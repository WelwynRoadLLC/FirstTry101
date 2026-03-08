"""
data.ai (App Annie) API client for fetching app store statistics.

Requires a data.ai Intelligence subscription and API key set as DATA_AI_API_KEY.
API docs: https://docs.data.ai/docs/intelligence-api
"""

import requests
import pandas as pd
from datetime import date
from config import FINTECH_APPS, METRIC_MAP


BASE_URL = "https://api.data.ai/v1.3/intelligence"


class DataAIClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "DATA_AI_API_KEY is not set. Add it to your .env file.\n"
                "See .env.example for the required format."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    def get_app_history(
        self,
        app_name: str,
        metric: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Fetch monthly metric history for a single app.

        Args:
            app_name:   Key from FINTECH_APPS (e.g. "Cash App")
            metric:     One of "Downloads", "DAU", "MAU"
            start_date: Start of period (inclusive)
            end_date:   End of period (inclusive)

        Returns:
            DataFrame with columns: date (datetime), app_name (str), value (float)
        """
        if app_name not in FINTECH_APPS:
            raise ValueError(f"Unknown app: {app_name}. Check config.py FINTECH_APPS.")

        if metric not in METRIC_MAP:
            raise ValueError(f"Unknown metric: {metric}. Use one of {list(METRIC_MAP.keys())}")

        app_cfg = FINTECH_APPS[app_name]
        app_id = app_cfg["ios_app_id"]
        platform = app_cfg["platform"]

        device = "iphone" if platform == "ios" else "android_phone"

        url = f"{BASE_URL}/apps/{app_id}/app_history/"
        params = {
            "country": "US",
            "granularity": "monthly",
            "device": device,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "feeds": METRIC_MAP[metric],
        }

        response = self.session.get(url, params=params, timeout=30)

        if response.status_code == 401:
            raise PermissionError(
                "data.ai API returned 401 Unauthorized. "
                "Check that your DATA_AI_API_KEY is valid."
            )
        if response.status_code == 403:
            raise PermissionError(
                "data.ai API returned 403 Forbidden. "
                "Your subscription may not include this metric or app."
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"data.ai API error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        records = data.get("list", [])

        if not records:
            return pd.DataFrame(columns=["date", "app_name", "value"])

        df = pd.DataFrame(records)
        df = df.rename(columns={"timestamp": "date", METRIC_MAP[metric]: "value"})
        df["date"] = pd.to_datetime(df["date"])
        df["app_name"] = app_name
        df["value"] = pd.to_numeric(df["value"], errors="coerce")

        return df[["date", "app_name", "value"]]

    def get_multi_app(
        self,
        app_names: list[str],
        metric: str,
        start_date: date,
        end_date: date,
    ) -> pd.DataFrame:
        """
        Fetch and combine metric history for multiple apps.

        Returns a single DataFrame with columns: date, app_name, value
        """
        frames = []
        errors = []

        for name in app_names:
            try:
                df = self.get_app_history(name, metric, start_date, end_date)
                frames.append(df)
            except Exception as e:
                errors.append(f"{name}: {e}")

        if errors:
            # Surface errors but still return whatever succeeded
            raise RuntimeError(
                "Some apps failed to load:\n" + "\n".join(errors)
            )

        if not frames:
            return pd.DataFrame(columns=["date", "app_name", "value"])

        return pd.concat(frames, ignore_index=True)
