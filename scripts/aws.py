#!/usr/bin/env python3
"""Prepare or provision an Agno sandbox. Uses Python's standard library, AWS CLI and Docker."""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

# Edit these non-secret settings before running plan or apply. Never put keys here.
AWS_PROFILE = "default"
EXPECTED_ACCOUNT_ID = ""  # Your 12-digit AWS account ID; checked before any AWS changes.
AWS_REGION = "us-east-1"
DEPLOYMENT_NAME = "agentos-sandbox"  # Keep this stable when updating the image.
BUCKET_NAME = ""  # Empty derives a name from the deployment, account and region.
CHECKPOINT_PREFIX = "agentos/checkpoints/"

ROOT = Path(__file__).resolve().parents[1]
OWNER = "agno-template-sandbox"


def load_config():
    config = {
        "profile": AWS_PROFILE,
        "account_id": EXPECTED_ACCOUNT_ID,
        "region": AWS_REGION,
        "stack_name": DEPLOYMENT_NAME,
        "bucket_name": BUCKET_NAME or f"{DEPLOYMENT_NAME}-{EXPECTED_ACCOUNT_ID}-{AWS_REGION}",
        "checkpoint_prefix": CHECKPOINT_PREFIX,
        "ecr_repository": DEPLOYMENT_NAME,
        "runtime_name": DEPLOYMENT_NAME.replace("-", "_"),
        "source_dir": str(ROOT),
    }
    if not EXPECTED_ACCOUNT_ID:
        raise ValueError("Set EXPECTED_ACCOUNT_ID and AWS_PROFILE near the top of scripts/aws.py first")
    patterns = {
        "profile": r"[\w.-]+",
        "account_id": r"[0-9]{12}",
        "region": r"[a-z]{2}(?:-[a-z]+)+-[0-9]+",
        "stack_name": r"[a-z][a-z0-9-]{0,31}",
        "bucket_name": r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]",
        "checkpoint_prefix": r"[A-Za-z0-9][A-Za-z0-9_/-]*/",
    }
    for key, pattern in patterns.items():
        if not isinstance(config[key], str) or not re.fullmatch(pattern, config[key]):
            raise ValueError(f"Invalid {key}; check the settings at the top of scripts/aws.py")
    if config["bucket_name"].startswith(("xn--", "sthree-", "amzn-s3-demo-")) or config["bucket_name"].endswith(
        "--x-s3"
    ):
        raise ValueError("BUCKET_NAME uses a reserved S3 prefix or suffix")
    if not (ROOT / "Dockerfile").is_file():
        raise ValueError("Run this script from a template checkout containing its Dockerfile")
    return config


class Setup:
    def __init__(self, config):
        self.config = config
        self.environment = dict(os.environ, AWS_PAGER="")
        # The named profile, not ambient exported keys, must select the account.
        for key in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_SECURITY_TOKEN",
        ):
            self.environment.pop(key, None)
        self.aws = [
            "aws",
            "--profile",
            config["profile"],
            "--region",
            config["region"],
            "--no-cli-pager",
        ]

    def read(self, *args):
        result = subprocess.run(
            [*self.aws, *args, "--output", "json"],
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return json.loads(result.stdout)

    def verify_account(self):
        identity = self.read("sts", "get-caller-identity")
        if identity["Account"] != self.config["account_id"]:
            raise RuntimeError(f"Wrong AWS account: expected {self.config['account_id']}, got {identity['Account']}")

    def existing_stack(self, name):
        try:
            stack = self.read("cloudformation", "describe-stacks", "--stack-name", name)["Stacks"][0]
        except RuntimeError as error:
            if "ValidationError" in str(error) and "does not exist" in str(error):
                return None
            raise
        tags = {t["Key"]: t["Value"] for t in stack.get("Tags", [])}
        if tags.get("ManagedBy") != OWNER:
            raise RuntimeError(f"Refusing to change unrelated stack {name}")
        return stack

    def check_update(self, name, parameters):
        stack = self.existing_stack(name)
        if stack:
            status = stack["StackStatus"]
            if status not in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}:
                raise RuntimeError(f"Stack {name} is {status}; inspect its CloudFormation events before retrying")
            old = {p["ParameterKey"]: p["ParameterValue"] for p in stack.get("Parameters", [])}
            for key in ("BucketName", "RepositoryName", "RuntimeName", "CheckpointPrefix"):
                if key in old and key in parameters and parameters[key] != old[key]:
                    raise RuntimeError(f"Changing {key} on {name} needs a migration; use a new DEPLOYMENT_NAME")

    def deploy_stack(self, name, template, parameters):
        self.check_update(name, parameters)
        with NamedTemporaryFile(mode="w", suffix=".yaml") as template_file:
            template_file.write(template)
            template_file.flush()
            subprocess.run(
                [
                    *self.aws,
                    "cloudformation",
                    "deploy",
                    "--stack-name",
                    name,
                    "--template-file",
                    template_file.name,
                    "--capabilities",
                    "CAPABILITY_IAM",
                    "--no-fail-on-empty-changeset",
                    "--tags",
                    f"ManagedBy={OWNER}",
                    "--parameter-overrides",
                    *(f"{k}={v}" for k, v in parameters.items()),
                ],
                env=self.environment,
                check=True,
            )
        return self.outputs(name)

    def outputs(self, name):
        stack = self.existing_stack(name)
        if not stack:
            raise RuntimeError(f"Stack {name} does not exist; run apply first")
        return {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}

    def status(self):
        name = self.config["stack_name"]
        foundation = self.existing_stack(name + "-foundation")
        runtime = self.existing_stack(name + "-runtime")
        result = {
            "FoundationStackStatus": foundation["StackStatus"] if foundation else "NOT_CREATED",
            "RuntimeStackStatus": runtime["StackStatus"] if runtime else "NOT_CREATED",
        }
        if runtime:
            result.update({o["OutputKey"]: o["OutputValue"] for o in runtime.get("Outputs", [])})
        if "RuntimeId" in result:
            result["RuntimeStatus"] = self.read(
                "bedrock-agentcore-control", "get-agent-runtime", "--agent-runtime-id", result["RuntimeId"]
            )["status"]
            result["EndpointStatus"] = self.read(
                "bedrock-agentcore-control",
                "get-agent-runtime-endpoint",
                "--agent-runtime-id",
                result["RuntimeId"],
                "--endpoint-name",
                "DEFAULT",
            )["status"]
        return result

    def wait_ready(self, runtime_id):
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            runtime = self.read(
                "bedrock-agentcore-control",
                "get-agent-runtime",
                "--agent-runtime-id",
                runtime_id,
            )
            endpoint = self.read(
                "bedrock-agentcore-control",
                "get-agent-runtime-endpoint",
                "--agent-runtime-id",
                runtime_id,
                "--endpoint-name",
                "DEFAULT",
            )
            states = (runtime["status"], endpoint["status"])
            if states == ("READY", "READY"):
                return
            if any("FAILED" in state or state.startswith("DELET") for state in states):
                raise RuntimeError(f"Runtime/endpoint failed: {states}; inspect AgentCore and CloudFormation events")
            print(f"Runtime / DEFAULT endpoint: {states}; waiting...", flush=True)
            time.sleep(10)
        raise RuntimeError("Timed out waiting for runtime/endpoint readiness; resources were left for inspection")

    def apply(self):
        c = self.config
        self.verify_account()
        subprocess.run(["docker", "info"], check=True, capture_output=True)
        # Validate both stacks before provisioning or uploading a new image.
        self.check_update(
            c["stack_name"] + "-runtime",
            {
                "RuntimeName": c["runtime_name"],
                "BucketName": c["bucket_name"],
                "CheckpointPrefix": c["checkpoint_prefix"],
            },
        )
        self.check_update(
            c["stack_name"] + "-foundation",
            {
                "RuntimeName": c["runtime_name"],
                "BucketName": c["bucket_name"],
                "RepositoryName": c["ecr_repository"],
            },
        )
        foundation = self.deploy_stack(
            c["stack_name"] + "-foundation",
            FOUNDATION_TEMPLATE,
            {
                "BucketName": c["bucket_name"],
                "RepositoryName": c["ecr_repository"],
                "RuntimeName": c["runtime_name"],
            },
        )
        repository = foundation["RepositoryUri"]
        tag = f"build-{time.strftime('%Y%m%d%H%M%S', time.gmtime())}-{uuid4().hex[:8]}"
        image = repository + ":" + tag
        password = subprocess.run(
            [*self.aws, "ecr", "get-login-password"],
            env=self.environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        # Use Docker's configured credential helper; the token travels over stdin.
        subprocess.run(
            [
                "docker",
                "login",
                "--username",
                "AWS",
                "--password-stdin",
                repository.split("/")[0],
            ],
            input=password,
            text=True,
            env=self.environment,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "docker",
                "build",
                "--platform",
                "linux/arm64",
                "--load",
                "--target",
                "sandbox",
                "--tag",
                image,
                c["source_dir"],
            ],
            env=self.environment,
            check=True,
        )
        subprocess.run(["docker", "push", image], env=self.environment, check=True)
        result = self.deploy_stack(
            c["stack_name"] + "-runtime",
            RUNTIME_TEMPLATE,
            {
                "RuntimeName": c["runtime_name"],
                "ImageUri": image,
                "ExecutionRoleArn": foundation["ExecutionRoleArn"],
                "BucketName": c["bucket_name"],
                "CheckpointPrefix": c["checkpoint_prefix"],
            },
        )
        self.wait_ready(result["RuntimeId"])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "apply", "status"))
    args = parser.parse_args()
    config = load_config()
    if args.action == "plan":
        print("Local configuration preview only; no AWS calls or resources created.")
        print(json.dumps(config, indent=2))
        print("Creates/updates two CloudFormation stacks: <stack_name>-foundation and <stack_name>-runtime.")
        print(
            "Resources: private checkpoint bucket, ECR repository, execution role, HTTP runtime, restricted IAM user."
        )
        print("Builds the Dockerfile sandbox target for ARM64. Creates no access keys. AWS usage incurs charges.")
        return
    setup = Setup(config)
    if args.action == "apply":
        result = setup.apply()
    else:
        setup.verify_account()
        result = setup.status()
    print(json.dumps(result, indent=2))
    if not all(key in result for key in ("RuntimeArn", "CheckpointBucket", "CheckpointPrefix", "ApplicationUser")):
        print("No complete runtime configuration yet. Run apply for a new setup, or inspect CloudFormation events.")
        return
    print("\nSet REPOSITORY to your GitHub URL and branch in app/sandbox.py, then use:")
    print("def sandbox_provider() -> Sandbox | None:")
    print("    return agentcore_sandbox(")
    for argument, key in (
        ("runtime_arn", "RuntimeArn"),
        ("checkpoint_bucket", "CheckpointBucket"),
        ("checkpoint_prefix", "CheckpointPrefix"),
    ):
        print(f"        {argument}={result[key]!r},")
    print("    )")
    print("Your API needs credentials for ApplicationUser and AWS_DEFAULT_REGION=" + config["region"])
    print("Create the user access key in IAM and enter it directly in your API host's secret settings.")
    print("See docs/harnesses.md for credentials, deployment, recovery testing and cleanup.")
    print("No model execution or checkpoint recovery test has been performed.")


# CloudFormation owns the resources; keep templates here so setup is a single file.
FOUNDATION_TEMPLATE = """\
AWSTemplateFormatVersion: '2010-09-09'
Description: Image storage, checkpoint storage and execution role for an Agno sandbox.
Parameters:
  BucketName:
    Type: String
  RepositoryName:
    Type: String
  RuntimeName:
    Type: String
Resources:
  Checkpoints:
    Type: AWS::S3::Bucket
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      BucketName: !Ref BucketName
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        IgnorePublicAcls: true
        BlockPublicPolicy: true
        RestrictPublicBuckets: true
      OwnershipControls:
        Rules:
          - ObjectOwnership: BucketOwnerEnforced
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: AES256
      LifecycleConfiguration:
        Rules:
          - Id: AbortIncompleteUploads
            Status: Enabled
            AbortIncompleteMultipartUpload:
              DaysAfterInitiation: 7
  CheckpointPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref Checkpoints
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Deny
            Principal: '*'
            Action: 's3:*'
            Resource:
              - !GetAtt Checkpoints.Arn
              - !Sub '${Checkpoints.Arn}/*'
            Condition:
              Bool:
                aws:SecureTransport: 'false'
  Images:
    Type: AWS::ECR::Repository
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      RepositoryName: !Ref RepositoryName
      ImageTagMutability: IMMUTABLE
      EncryptionConfiguration:
        EncryptionType: AES256
      ImageScanningConfiguration:
        ScanOnPush: true
  ExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: bedrock-agentcore.amazonaws.com
            Action: sts:AssumeRole
            Condition:
              StringEquals:
                aws:SourceAccount: !Ref AWS::AccountId
              ArnLike:
                aws:SourceArn: !Sub 'arn:${AWS::Partition}:bedrock-agentcore:${AWS::Region}:${AWS::AccountId}:*'
      Policies:
        - PolicyName: PullImageAndWriteLogs
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: [ecr:BatchGetImage, ecr:GetDownloadUrlForLayer]
                Resource: !GetAtt Images.Arn
              - Effect: Allow
                Action: ecr:GetAuthorizationToken
                Resource: '*'
              - Effect: Allow
                Action: [logs:CreateLogGroup, logs:DescribeLogStreams]
                Resource: !Sub
                  - 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${LogName}'
                  - LogName: !Sub '/aws/bedrock-agentcore/runtimes/${RuntimeName}-*'
              - Effect: Allow
                Action: [logs:CreateLogStream, logs:PutLogEvents]
                Resource: !Sub
                  - 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:${LogName}:log-stream:*'
                  - LogName: !Sub '/aws/bedrock-agentcore/runtimes/${RuntimeName}-*'
Outputs:
  BucketName:
    Value: !Ref Checkpoints
  RepositoryUri:
    Value: !GetAtt Images.RepositoryUri
  ExecutionRoleArn:
    Value: !GetAtt ExecutionRole.Arn
"""

RUNTIME_TEMPLATE = """\
AWSTemplateFormatVersion: '2010-09-09'
Description: Agno sandbox runtime and a restricted identity for its API caller.
Parameters:
  RuntimeName:
    Type: String
  ImageUri:
    Type: String
  ExecutionRoleArn:
    Type: String
  BucketName:
    Type: String
  CheckpointPrefix:
    Type: String
Resources:
  Runtime:
    Type: AWS::BedrockAgentCore::Runtime
    Properties:
      AgentRuntimeName: !Ref RuntimeName
      AgentRuntimeArtifact:
        ContainerConfiguration:
          ContainerUri: !Ref ImageUri
      RoleArn: !Ref ExecutionRoleArn
      NetworkConfiguration:
        NetworkMode: PUBLIC
      ProtocolConfiguration: HTTP
      LifecycleConfiguration:
        IdleRuntimeSessionTimeout: 900
        MaxLifetime: 3600
  ApplicationCaller:
    Type: AWS::IAM::User
    Properties:
      Policies:
        - PolicyName: UseSandboxAndCheckpoints
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action:
                  - bedrock-agentcore:InvokeAgentRuntime
                  - bedrock-agentcore:InvokeAgentRuntimeCommand
                  - bedrock-agentcore:StopRuntimeSession
                Resource:
                  - !GetAtt Runtime.AgentRuntimeArn
                  - !Sub '${Runtime.AgentRuntimeArn}/runtime-endpoint/DEFAULT'
              - Effect: Allow
                Action: [s3:GetObject, s3:PutObject, s3:DeleteObject, s3:AbortMultipartUpload]
                Resource: !Sub 'arn:${AWS::Partition}:s3:::${BucketName}/${CheckpointPrefix}*'
              - Effect: Allow
                Action: s3:ListBucket
                Resource: !Sub 'arn:${AWS::Partition}:s3:::${BucketName}'
Outputs:
  RuntimeArn:
    Value: !GetAtt Runtime.AgentRuntimeArn
  RuntimeId:
    Value: !GetAtt Runtime.AgentRuntimeId
  ApplicationUser:
    Value: !Ref ApplicationCaller
  CheckpointBucket:
    Value: !Ref BucketName
  CheckpointPrefix:
    Value: !Ref CheckpointPrefix
  AwsRegion:
    Value: !Ref AWS::Region
"""


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
