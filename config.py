import os
from dotenv import load_dotenv

load_dotenv()

DATA_AI_API_KEY = os.getenv("DATA_AI_API_KEY", "")

# Fintech app registry: name → iOS App Store ID and Android bundle ID
# iOS IDs are used as primary identifiers for data.ai API calls
FINTECH_APPS = {
    "Cash App": {
        "ios_app_id": "711923939",
        "android_bundle_id": "com.squareup.cash",
        "platform": "ios",
    },
    "Chime": {
        "ios_app_id": "836215269",
        "android_bundle_id": "com.onedebit.chime",
        "platform": "ios",
    },
    "Current": {
        "ios_app_id": "1177050553",
        "android_bundle_id": "com.current.app",
        "platform": "ios",
    },
    "Venmo": {
        "ios_app_id": "351727428",
        "android_bundle_id": "com.venmo",
        "platform": "ios",
    },
    "PayPal": {
        "ios_app_id": "283646709",
        "android_bundle_id": "com.paypal.android.p2pmobile",
        "platform": "ios",
    },
    "Dave": {
        "ios_app_id": "1199462234",
        "android_bundle_id": "com.dave",
        "platform": "ios",
    },
    "Revolut": {
        "ios_app_id": "1087547462",
        "android_bundle_id": "com.revolut.revolut",
        "platform": "ios",
    },
    "Robinhood": {
        "ios_app_id": "938003185",
        "android_bundle_id": "com.robinhood.android",
        "platform": "ios",
    },
    "Zelle": {
        "ios_app_id": "1260755201",
        "android_bundle_id": "com.zellepay.zelle",
        "platform": "ios",
    },
    "SoFi": {
        "ios_app_id": "1191985736",
        "android_bundle_id": "com.sofi.mobile",
        "platform": "ios",
    },
    "Klarna": {
        "ios_app_id": "1115120118",
        "android_bundle_id": "com.myklarna.android",
        "platform": "ios",
    },
    "Affirm": {
        "ios_app_id": "1232016608",
        "android_bundle_id": "com.affirm.affirm",
        "platform": "ios",
    },
}

# data.ai metric key mapping
METRIC_MAP = {
    "Downloads": "units_download",
    "DAU": "units_dau",
    "MAU": "units_mau",
}

# Bloomberg-inspired color palette for chart lines
LINE_COLORS = [
    "#00d4ff",  # cyan
    "#ff6b35",  # orange
    "#7fff00",  # chartreuse
    "#ff00ff",  # magenta
    "#ffd700",  # gold
    "#ff4444",  # red
    "#00ff99",  # green
    "#a78bfa",  # purple
    "#fb923c",  # amber
    "#f472b6",  # pink
]
