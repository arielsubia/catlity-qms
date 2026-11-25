from datetime import datetime

from pydantic import BaseModel


class EmbedUrlResponse(BaseModel):
    """Temporary URL that opens the KPI dashboard inside the app.

    ``expires_at`` is when the QuickSight session ends. The page requests a
    new URL before that moment. The URL itself must be opened within five
    minutes of this response; that limit is fixed by QuickSight.
    """

    embed_url: str
    expires_at: datetime
