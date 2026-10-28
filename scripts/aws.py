#!/usr/bin/env python3
"""Provision AWS AgentCore sandboxes and S3 checkpoints for your agent platform."""

import base64
import re
import subprocess
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3  # type: ignore[import-untyped]
import typer
from botocore.exceptions import BotoCoreError, ClientError, WaiterError  # type: ignore[import-untyped]
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

# Your AWS account and resource names. Keep credentials in your AWS profile.
AWS_PROFILE = "default"
EXPECTED_ACCOUNT_ID = ""  # Set your 12-digit account ID before running the script.
AWS_REGION = "us-east-1"
DEPLOYMENT_NAME = "agentos-sandbox"
BUCKET_NAME = ""  # Leave empty to derive a name from the deployment, account and region.
CHECKPOINT_PREFIX = "agentos/checkpoints/"

ROOT = Path(__file__).resolve().parents[1]
OWNER = "agno-template-sandbox"
console = Console()
app = typer.Typer(
    help=__doc__,
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)


@app.command()
def plan() -> None:
    """Preview the configuration without connecting to AWS."""
    with report_errors():
        validate_settings()
        show_table(
            "AWS sandbox plan",
            {
                "Profile": AWS_PROFILE,
                "Account": EXPECTED_ACCOUNT_ID,
                "Region": AWS_REGION,
                "Deployment": DEPLOYMENT_NAME,
                "Checkpoint bucket": checkpoint_bucket(),
                "Checkpoint prefix": CHECKPOINT_PREFIX,
                "Image repository": DEPLOYMENT_NAME,
                "Runtime": runtime_name(),
            },
        )
        console.print("Creates ECR, an AgentCore runtime, a private S3 bucket, and scoped IAM permissions.")
        console.print("[dim]Offline preview. Apply creates billable resources; it does not create access keys.[/dim]")


@app.command()
def apply() -> None:
    """Create or update the sandbox resources and upload the image."""
    with report_errors():
        validate_settings()
        deployment = SandboxDeployment()
        deployment.verify_account()
        deployment.check_existing_stacks()
        run_docker("info", quiet=True)
        show_connection(deployment.provision())


@app.command()
def status() -> None:
    """Show resource states and the configuration for your API."""
    with report_errors():
        validate_settings()
        deployment = SandboxDeployment()
        deployment.verify_account()
        show_connection(deployment.inspect())


def checkpoint_bucket() -> str:
    return BUCKET_NAME or f"{DEPLOYMENT_NAME}-{EXPECTED_ACCOUNT_ID}-{AWS_REGION}"


def runtime_name() -> str:
    return DEPLOYMENT_NAME.replace("-", "_")


def validate_settings() -> None:
    """Catch configuration mistakes before connecting to AWS or starting Docker."""
    settings = {
        "AWS_PROFILE": (AWS_PROFILE, r"[\w.-]+"),
        "EXPECTED_ACCOUNT_ID": (EXPECTED_ACCOUNT_ID, r"[0-9]{12}"),
        "AWS_REGION": (AWS_REGION, r"[a-z]{2}(?:-[a-z]+)+-[0-9]+"),
        "DEPLOYMENT_NAME": (DEPLOYMENT_NAME, r"[a-z][a-z0-9-]{0,31}"),
        "BUCKET_NAME": (checkpoint_bucket(), r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]"),
        "CHECKPOINT_PREFIX": (CHECKPOINT_PREFIX, r"[A-Za-z0-9][A-Za-z0-9_/-]*/"),
    }
    for name, (value, pattern) in settings.items():
        if not re.fullmatch(pattern, value):
            raise ValueError(f"Set a valid {name} near the top of scripts/aws.py.")
    if checkpoint_bucket().startswith(("xn--", "sthree-", "amzn-s3-demo-")) or checkpoint_bucket().endswith(
        ("--x-s3", "--ol-s3", "--table-s3")
    ):
        raise ValueError("BUCKET_NAME uses a reserved S3 prefix or suffix.")
    if not (ROOT / "Dockerfile").is_file():
        raise ValueError("The template Dockerfile must be present beside scripts/.")


class SandboxDeployment:
    """Manage the storage stack, sandbox image, and runtime stack in one AWS account."""

    def __init__(self) -> None:
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        self.sts = session.client("sts")
        self.cloudformation = session.client("cloudformation")
        self.ecr = session.client("ecr")
        self.agentcore = session.client("bedrock-agentcore-control")
        self.foundation_stack = f"{DEPLOYMENT_NAME}-foundation"
        self.runtime_stack = f"{DEPLOYMENT_NAME}-runtime"
        self.foundation_parameters = {
            "BucketName": checkpoint_bucket(),
            "RepositoryName": DEPLOYMENT_NAME,
            "RuntimeName": runtime_name(),
        }
        self.runtime_parameters = {
            "BucketName": checkpoint_bucket(),
            "CheckpointPrefix": CHECKPOINT_PREFIX,
            "RuntimeName": runtime_name(),
        }

    def verify_account(self) -> None:
        account = self.sts.get_caller_identity()["Account"]
        if account != EXPECTED_ACCOUNT_ID:
            raise RuntimeError(f"Wrong AWS account: expected {EXPECTED_ACCOUNT_ID}, signed in to {account}.")

    def get_stack(self, name: str) -> dict[str, Any] | None:
        try:
            stack = self.cloudformation.describe_stacks(StackName=name)["Stacks"][0]
        except ClientError as error:
            details = error.response["Error"]
            if details["Code"] == "ValidationError" and "does not exist" in details["Message"]:
                return None
            raise
        tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
        if tags.get("ManagedBy") != OWNER:
            raise RuntimeError(f"Refusing to change unrelated stack {name}.")
        return stack

    def check_stack(self, name: str, parameters: dict[str, str]) -> dict[str, Any] | None:
        stack = self.get_stack(name)
        if stack is None:
            return None
        if stack["StackStatus"] not in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"}:
            raise RuntimeError(f"{name} is {stack['StackStatus']}. Inspect its CloudFormation events before retrying.")
        existing = {item["ParameterKey"]: item["ParameterValue"] for item in stack.get("Parameters", [])}
        for key in ("BucketName", "RepositoryName", "RuntimeName", "CheckpointPrefix"):
            if key in existing and key in parameters and parameters[key] != existing[key]:
                raise RuntimeError(f"Changing {key} needs a migration. Use a new DEPLOYMENT_NAME for a separate setup.")
        return stack

    def check_existing_stacks(self) -> None:
        self.check_stack(self.foundation_stack, self.foundation_parameters)
        self.check_stack(self.runtime_stack, self.runtime_parameters)

    def deploy_stack(self, name: str, template: str, parameters: dict[str, str]) -> dict[str, str]:
        existing = self.check_stack(name, parameters)
        request = {
            "StackName": name,
            "TemplateBody": template,
            "Parameters": [{"ParameterKey": key, "ParameterValue": value} for key, value in parameters.items()],
            "Capabilities": ["CAPABILITY_IAM"],
            "Tags": [{"Key": "ManagedBy", "Value": OWNER}],
        }
        if existing:
            try:
                self.cloudformation.update_stack(**request)
            except ClientError as error:
                details = error.response["Error"]
                if details["Code"] == "ValidationError" and "No updates are to be performed" in details["Message"]:
                    console.print(f"[dim]{name} is already up to date.[/dim]")
                    return stack_outputs(existing)
                raise
            waiter = self.cloudformation.get_waiter("stack_update_complete")
        else:
            self.cloudformation.create_stack(**request)
            waiter = self.cloudformation.get_waiter("stack_create_complete")
        with console.status(f"Waiting for {name}…"):
            try:
                waiter.wait(StackName=name, WaiterConfig={"Delay": 5, "MaxAttempts": 240})
            except WaiterError as error:
                raise RuntimeError(
                    f"{name} did not complete. Inspect its CloudFormation events before retrying."
                ) from error
        return stack_outputs(self.get_stack(name))

    def publish_image(self, repository: str) -> str:
        token = self.ecr.get_authorization_token()["authorizationData"][0]["authorizationToken"]
        username, password = base64.b64decode(token).decode().split(":", 1)
        run_docker(
            "login", "--username", username, "--password-stdin", repository.split("/")[0], stdin=password, quiet=True
        )
        image = f"{repository}:build-{uuid4().hex[:12]}"
        run_docker("build", "--platform", "linux/arm64", "--load", "--target", "sandbox", "--tag", image, str(ROOT))
        run_docker("push", image)
        return image

    def runtime_states(self, runtime_id: str) -> dict[str, str]:
        runtime = self.agentcore.get_agent_runtime(agentRuntimeId=runtime_id)
        try:
            endpoint = self.agentcore.get_agent_runtime_endpoint(agentRuntimeId=runtime_id, endpointName="DEFAULT")
            endpoint_status = endpoint["status"]
        except ClientError as error:
            if error.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            endpoint_status = "NOT_CREATED"
        return {"RuntimeStatus": runtime["status"], "EndpointStatus": endpoint_status}

    def wait_for_runtime(self, runtime_id: str) -> None:
        deadline = time.monotonic() + 1200
        with console.status("Waiting for the AgentCore runtime…") as progress:
            while time.monotonic() < deadline:
                states = self.runtime_states(runtime_id)
                if all(state == "READY" for state in states.values()):
                    return
                if any("FAILED" in state or state.startswith("DELET") for state in states.values()):
                    raise RuntimeError(f"AgentCore did not become ready: {states}. Inspect the runtime in AWS.")
                progress.update(f"Runtime: {states['RuntimeStatus']} · Endpoint: {states['EndpointStatus']}")
                time.sleep(10)
        raise RuntimeError("Timed out waiting for AgentCore. Resources remain available for inspection.")

    def provision(self) -> dict[str, str]:
        console.rule("1 · Create image and checkpoint storage")
        foundation = self.deploy_stack(self.foundation_stack, FOUNDATION_TEMPLATE, self.foundation_parameters)
        console.rule("2 · Build and publish the sandbox image")
        image = self.publish_image(foundation["RepositoryUri"])
        console.rule("3 · Create or update the AgentCore runtime")
        runtime = self.deploy_stack(
            self.runtime_stack,
            RUNTIME_TEMPLATE,
            {
                **self.runtime_parameters,
                "ImageUri": image,
                "ExecutionRoleArn": foundation["ExecutionRoleArn"],
            },
        )
        self.wait_for_runtime(runtime["RuntimeId"])
        console.print("[green]Sandbox resources are ready.[/green]")
        return runtime

    def inspect(self) -> dict[str, str]:
        foundation = self.get_stack(self.foundation_stack)
        runtime = self.get_stack(self.runtime_stack)
        result = {
            **stack_outputs(foundation),
            **stack_outputs(runtime),
            "FoundationStackStatus": foundation["StackStatus"] if foundation else "NOT_CREATED",
            "RuntimeStackStatus": runtime["StackStatus"] if runtime else "NOT_CREATED",
        }
        if "RuntimeId" in result:
            result.update(self.runtime_states(result["RuntimeId"]))
        return result


def stack_outputs(stack: dict[str, Any] | None) -> dict[str, str]:
    return {item["OutputKey"]: item["OutputValue"] for item in (stack or {}).get("Outputs", [])}


def run_docker(*args: str, stdin: str | None = None, quiet: bool = False) -> None:
    """Leave build progress visible; send the ECR password only over stdin."""
    result = subprocess.run(["docker", *args], input=stdin, text=True, capture_output=quiet, check=False)
    if result.returncode:
        raise RuntimeError(f"Docker {args[0]} failed (exit {result.returncode}). Check Docker and retry.")


def show_table(title: str, values: dict[str, str]) -> None:
    table = Table(title=title, show_header=False, title_style="bold cyan")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", overflow="fold")
    for label, value in values.items():
        table.add_row(Text(label), Text(value))
    console.print(table)


def show_connection(values: dict[str, str]) -> None:
    show_table("AWS sandbox", values)
    if not all(key in values for key in ("RuntimeArn", "CheckpointBucket", "CheckpointPrefix", "ApplicationUser")):
        console.print(
            "[yellow]Setup is incomplete. Run apply for a new setup, or inspect CloudFormation events.[/yellow]"
        )
        return
    snippet = f"""def sandbox_provider() -> Sandbox | None:
    return agentcore_sandbox(
        runtime_arn={values["RuntimeArn"]!r},
        checkpoint_bucket={values["CheckpointBucket"]!r},
        checkpoint_prefix={values["CheckpointPrefix"]!r},
    )"""
    console.print("\n[bold]Configure app/sandbox.py[/bold]")
    console.print("Set REPOSITORY to your GitHub URL and branch, then use:")
    width = max(len(line) for line in snippet.splitlines())
    console.print(Syntax(snippet, "python", code_width=width, word_wrap=False), soft_wrap=True)
    console.print(f"\nSet AWS_DEFAULT_REGION={AWS_REGION} on your API host.")
    console.print(
        "Create an access key for ApplicationUser in IAM and enter it directly in your host's secret settings."
    )
    console.print("[dim]Follow docs/harnesses.md to deploy the API, test checkpoint recovery, and clean up.[/dim]")


@contextmanager
def report_errors() -> Iterator[None]:
    try:
        yield
    except (BotoCoreError, ClientError, OSError, RuntimeError, ValueError) as error:
        console.print(Text(str(error), style="bold red"))
        raise typer.Exit(code=1) from None


# CloudFormation owns the resources; keep the declarations here so setup is one file.
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
    app()
