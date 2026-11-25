"""Temporary embed URL for the KPI dashboard.

The call is GenerateEmbedUrlForRegisteredUser. Anonymous embedding needs the
Reader session capacity pack, and that pack is not purchased. The Reader is
the QuickSight user whose name is the Cognito email. The console user invites
that Reader later. This module does not create the user or the subscription.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_SESSION_MINUTES = 15
UNAVAILABLE = "Dashboard is not available yet."


class QuickSightUnavailable(Exception):
    """The dashboard or the registered Reader cannot be embedded."""


def get_quicksight_client() -> Any:
    """QuickSight client for the API process. Tests override this dependency."""
    return boto3.client("quicksight", region_name=settings.aws_region)


def registered_user_arn(email: str) -> str:
    """ARN of the Reader invited under the Cognito email."""
    return (
        f"arn:aws:quicksight:{settings.aws_region}:{settings.quicksight_aws_account_id}:"
        f"user/{settings.quicksight_namespace}/{email}"
    )


def embed_dashboard(client: Any, *, email: str) -> tuple[str, datetime]:
    """Ask QuickSight for a dashboard URL that lasts 15 minutes.

    A missing Reader, a missing dashboard, or any other client error becomes
    the same unavailable result. The AWS message stays in the log.
    """
    cleaned = email.strip()
    if not cleaned:
        raise QuickSightUnavailable(UNAVAILABLE)

    try:
        response = client.generate_embed_url_for_registered_user(
            AwsAccountId=settings.quicksight_aws_account_id,
            UserArn=registered_user_arn(cleaned),
            SessionLifetimeInMinutes=EMBED_SESSION_MINUTES,
            ExperienceConfiguration={
                "Dashboard": {
                    "InitialDashboardId": settings.quicksight_dashboard_id,
                }
            },
            AllowedDomains=[settings.app_public_url.rstrip("/")],
        )
    except (ClientError, BotoCoreError) as exc:
        logger.warning("QuickSight embed URL was not issued: %s", exc)
        raise QuickSightUnavailable(UNAVAILABLE) from exc

    embed_url = response.get("EmbedUrl")
    if not isinstance(embed_url, str) or not embed_url:
        logger.warning("QuickSight embed response did not include EmbedUrl")
        raise QuickSightUnavailable(UNAVAILABLE)

    expires_at = datetime.now(UTC) + timedelta(minutes=EMBED_SESSION_MINUTES)
    return embed_url, expires_at
