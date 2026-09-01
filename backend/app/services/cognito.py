"""Amazon Cognito client wrapper for user administration.

Encapsulates the boto3 calls used to provision users in the Cognito User Pool
so the API layer stays free of AWS SDK details and is easy to mock in tests.
"""

from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


@lru_cache(maxsize=1)
def _client():  # pragma: no cover - thin boto3 factory
    return boto3.client("cognito-idp", region_name=settings.aws_region)


class CognitoError(Exception):
    """Raised when a Cognito administrative operation fails."""


def register_user(
    *,
    email: str,
    password: str,
    tenant_id: str,
    role: str,
) -> str:
    """Create a confirmed user in the pool and return its Cognito ``sub``.

    The user is created with the ``custom:tenant_id`` and ``custom:role``
    attributes and added to the group matching ``role`` so both the attribute
    and group-based checks resolve consistently.
    """
    client = _client()
    pool_id = settings.cognito_user_pool_id

    try:
        create_resp = client.admin_create_user(
            UserPoolId=pool_id,
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "custom:tenant_id", "Value": tenant_id},
                {"Name": "custom:role", "Value": role},
            ],
            MessageAction="SUPPRESS",
        )

        # Set a permanent password so the user can log in immediately.
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username=email,
            Password=password,
            Permanent=True,
        )

        client.admin_add_user_to_group(
            UserPoolId=pool_id,
            Username=email,
            GroupName=role,
        )
    except client.exceptions.UsernameExistsException as exc:
        raise CognitoError("A user with this email already exists") from exc
    except ClientError as exc:  # pragma: no cover - AWS errors
        raise CognitoError(str(exc)) from exc

    sub = ""
    for attr in create_resp.get("User", {}).get("Attributes", []):
        if attr.get("Name") == "sub":
            sub = attr.get("Value", "")
            break
    return sub
