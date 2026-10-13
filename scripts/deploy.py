"""Create or update a CloudFormation stack with the AWS SDK (boto3)."""
import argparse
import sys

import boto3
from botocore.exceptions import ClientError, WaiterError


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stack-name", required=True)
    p.add_argument("--template", required=True)
    p.add_argument("--param", action="append", default=[], help="Key=Value")
    a = p.parse_args()

    cfn = boto3.client("cloudformation")
    with open(a.template, encoding="utf-8") as f:
        body = f.read()
    params = [
        {"ParameterKey": k, "ParameterValue": v}
        for k, v in (s.split("=", 1) for s in a.param)
    ]

    try:
        cfn.describe_stacks(StackName=a.stack_name)
        exists = True
    except ClientError as e:
        if "does not exist" not in str(e):
            raise
        exists = False

    kw = dict(StackName=a.stack_name, TemplateBody=body, Parameters=params)
    try:
        if exists:
            cfn.update_stack(**kw)
            waiter = cfn.get_waiter("stack_update_complete")
        else:
            cfn.create_stack(**kw)
            waiter = cfn.get_waiter("stack_create_complete")
        waiter.wait(StackName=a.stack_name)
    except ClientError as e:
        if "No updates are to be performed" in str(e):
            print("No changes.")
            return
        raise
    except WaiterError as e:
        print(f"Deployment failed: {e}", file=sys.stderr)
        sys.exit(1)

    for o in cfn.describe_stacks(StackName=a.stack_name)["Stacks"][0].get("Outputs", []):
        print(f"{o['OutputKey']} = {o['OutputValue']}")


if __name__ == "__main__":
    main()
