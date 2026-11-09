"""API client for Sri Lanka Telecom (SLT) MySLT API."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_LOGGER = logging.getLogger(__name__)

CLIENT_ID = "b7402e9d66808f762ccedbe42c20668e"
BASE_URL = "https://omniscapp.slt.lk/slt/ext/api/"


class SLTError(Exception):
    """Base exception for SLT API errors."""


class SLTAuthError(SLTError):
    """Exception for authentication errors."""


class SLTConnectionError(SLTError):
    """Exception for connection or gateway errors."""


class SLTDataError(SLTError):
    """Exception for unexpected data structure errors."""


class SLTApi:
    """Synchronous API client for SLT MySLT API."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the SLT API client."""
        self.username = username
        self.password = password
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.token_expiry: datetime | None = None

    def login(self) -> None:
        """Log in to MySLT API and retrieve access and refresh tokens."""
        url = f"{BASE_URL}Account/Login"
        headers = {
            "x-ibm-client-id": CLIENT_ID,
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://myslt.slt.lk",
            "Referer": "https://myslt.slt.lk/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        data = urllib.parse.urlencode(
            {
                "username": self.username,
                "password": self.password,
                "channelID": "WEB",
            }
        ).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
                res = json.loads(body)
        except urllib.error.HTTPError as err:
            if err.code in (400, 401, 403):
                raise SLTAuthError("Invalid username or password.") from err
            raise SLTConnectionError(f"HTTP error during login: {err.code}") from err
        except Exception as err:
            raise SLTConnectionError(f"Failed to connect to SLT API: {err}") from err

        if "accessToken" not in res or not res["accessToken"]:
            error_msg = res.get("errorShow") or res.get("errorMessege") or "Login failed"
            raise SLTAuthError(f"SLT Authentication failed: {error_msg}")

        self.access_token = res["accessToken"]
        self.refresh_token = res.get("refreshToken")
        # Token is valid for 3600 seconds by default; refresh 5 minutes early
        expires_in = res.get("expiresIn", 3600)
        self.token_expiry = datetime.now() + timedelta(seconds=max(expires_in - 300, 60))
        _LOGGER.debug("SLT API login successful, token expires at %s", self.token_expiry)

    def _ensure_authenticated(self) -> None:
        """Ensure an active, non-expired access token is available."""
        if not self.access_token or not self.token_expiry or datetime.now() >= self.token_expiry:
            self.login()

    def _request(
        self,
        endpoint: str,
        params: dict[str, str] | None = None,
        retry_on_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated GET request to the SLT API."""
        self._ensure_authenticated()

        url = f"{BASE_URL}{endpoint}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = {
            "x-ibm-client-id": CLIENT_ID,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        }

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 401 and retry_on_auth:
                _LOGGER.debug("Access token expired (401), re-authenticating and retrying")
                self.login()
                return self._request(endpoint, params, retry_on_auth=False)
            raise SLTConnectionError(f"HTTP error {err.code} from {endpoint}") from err
        except Exception as err:
            raise SLTConnectionError(f"Network error calling {endpoint}: {err}") from err

    def get_accounts(self) -> list[dict[str, Any]]:
        """Fetch all connections/accounts attached to this MySLT login."""
        res = self._request(
            "AccountOMNI/GetAccountDetailRequest",
            {"username": self.username},
        )
        if not res.get("isSuccess"):
            raise SLTDataError(res.get("errorShow") or "Failed to fetch accounts list.")
        return res.get("dataBundle") or []

    def get_service_detail(self, telephone_no: str) -> dict[str, Any] | None:
        """Fetch service details for a specific telephone connection."""
        res = self._request(
            "AccountOMNI/GetServiceDetailRequest",
            {"telephoneNo": telephone_no},
        )
        if res.get("isSuccess"):
            return res.get("dataBundle")
        return None

    def get_bill(self, account_no: str, telephone_no: str) -> dict[str, Any] | None:
        """Fetch bill information for a specific connection."""
        res = self._request(
            "AccountOMNI/BillPaymentRequest",
            {"telephoneNo": telephone_no, "accountNo": account_no},
        )
        if res.get("isSuccess"):
            return res.get("dataBundle")
        return None

    def get_usage(self, subscriber_id: str) -> dict[str, Any] | None:
        """Fetch broadband quota usage for a subscriber ID."""
        res = self._request(
            "BBVAS/UsageSummary",
            {"subscriberID": subscriber_id},
        )
        if res.get("isSuccess"):
            return res.get("dataBundle")
        return None

    def fetch_connection_data(
        self, account_no: str, telephone_no: str, status: str = "ACTIVE"
    ) -> dict[str, Any]:
        """Fetch complete aggregated data for a single telephone connection."""
        svc_detail = self.get_service_detail(telephone_no)
        bill_detail = self.get_bill(account_no, telephone_no)

        # Parse billing inquiry
        bill_amount: float | None = None
        outstanding_balance: float | None = None
        last_bill_date: str | None = None
        payment_due_date: str | None = None
        last_payment_date: str | None = None
        last_payment_amount: float | None = None

        if bill_detail and bill_detail.get("listofbillingInquiryType"):
            inquiries = bill_detail["listofbillingInquiryType"]
            if inquiries and isinstance(inquiries, list):
                b_info = inquiries[0]
                try:
                    bill_amount = float(b_info.get("billAmount", 0))
                except (ValueError, TypeError):
                    bill_amount = None

                try:
                    outstanding_balance = float(b_info.get("outstandingBalance", 0))
                except (ValueError, TypeError):
                    outstanding_balance = None

                try:
                    last_payment_amount = float(b_info.get("lastPaymentAmount", 0))
                except (ValueError, TypeError):
                    last_payment_amount = None

                last_bill_date = b_info.get("lastBillDate")
                payment_due_date = b_info.get("paymentDueDate")
                last_payment_date = b_info.get("lastPaymentDate")

        # Parse service details
        customer_name: str | None = None
        promotion_name: str | None = None
        promotion_type: str | None = None
        has_broadband = False
        bb_subscriber_id: str | None = None

        if svc_detail:
            customer_name = svc_detail.get("contactNamewithInit")
            promotion_name = svc_detail.get("promotionName")
            promotion_type = svc_detail.get("promotionType")

            bb_list = svc_detail.get("listofBBService") or []
            if bb_list and isinstance(bb_list, list) and len(bb_list) > 0:
                has_broadband = True
                bb_subscriber_id = bb_list[0].get("serviceID")

        # Parse broadband usage if broadband service exists
        bb_package_name: str | None = None
        data_used: float | None = None
        data_limit: float | None = None
        data_remaining: float | None = None
        data_unit = "GB"
        billing_cycle_expiry: str | None = None
        usage_status: str | None = None

        if has_broadband and bb_subscriber_id:
            usage_data = self.get_usage(bb_subscriber_id)
            if usage_data:
                usage_status = usage_data.get("status")
                pkg_summary = usage_data.get("my_package_summary") or {}
                pkg_info = usage_data.get("my_package_info") or {}

                bb_package_name = pkg_info.get("package_name")

                try:
                    if pkg_summary.get("used") is not None:
                        data_used = float(pkg_summary["used"])
                except (ValueError, TypeError):
                    pass

                try:
                    if pkg_summary.get("limit") is not None:
                        data_limit = float(pkg_summary["limit"])
                except (ValueError, TypeError):
                    pass

                data_unit = pkg_summary.get("volume_unit") or "GB"

                usage_details = pkg_info.get("usageDetails") or []
                if usage_details and isinstance(usage_details, list):
                    first_detail = usage_details[0]
                    billing_cycle_expiry = first_detail.get("expiry_date")
                    try:
                        if first_detail.get("remaining") is not None:
                            data_remaining = float(first_detail["remaining"])
                    except (ValueError, TypeError):
                        pass

        return {
            "account_number": account_no,
            "telephone_number": telephone_no,
            "status": status,
            "customer_name": customer_name,
            "promotion_name": promotion_name,
            "promotion_type": promotion_type,
            "outstanding_balance": outstanding_balance,
            "bill_amount": bill_amount,
            "payment_due_date": payment_due_date,
            "last_bill_date": last_bill_date,
            "last_payment_date": last_payment_date,
            "last_payment_amount": last_payment_amount,
            "has_broadband": has_broadband,
            "broadband_package": bb_package_name,
            "data_used": data_used,
            "data_limit": data_limit,
            "data_remaining": data_remaining,
            "data_unit": data_unit,
            "billing_cycle_expiry": billing_cycle_expiry,
            "usage_status": usage_status,
            "last_synced": datetime.now().isoformat(),
        }

