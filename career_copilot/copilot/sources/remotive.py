import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import JobDTO, JobSource


def _clean_html(raw_html: str) -> str:
    """Strip basic HTML tags and normalize whitespace."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())


def _parse_salary(salary_str: str) -> Tuple[Optional[int], Optional[int], str]:
    """
    Best-effort parsing of salary strings like '$80k - $120k', 'INR 1800000 - 2400000',
    '18-24 LPA', or '$90,000'. Returns (salary_min, salary_max, currency).
    """
    if not salary_str:
        return None, None, ""

    text = salary_str.strip()

    currency = ""
    if "₹" in text or "INR" in text.upper() or "LPA" in text.upper() or "LAKH" in text.upper():
        currency = "INR"
    elif "$" in text or "USD" in text.upper():
        currency = "USD"
    elif "€" in text or "EUR" in text.upper():
        currency = "EUR"
    elif "£" in text or "GBP" in text.upper():
        currency = "GBP"

    # LPA / Lakh handling (e.g. "18-24 LPA" or "20 LPA")
    lpa_match = re.findall(r"(\d+(?:\.\d+)?)\s*(?:-|to)?\s*(\d+(?:\.\d+)?)\s*(?:LPA|LAKH)", text, re.IGNORECASE)
    if lpa_match:
        val1, val2 = lpa_match[0]
        s_min = int(float(val1) * 100000)
        s_max = int(float(val2) * 100000)
        return min(s_min, s_max), max(s_min, s_max), currency or "INR"

    single_lpa = re.findall(r"(\d+(?:\.\d+)?)\s*(?:LPA|LAKH)", text, re.IGNORECASE)
    if single_lpa:
        val = int(float(single_lpa[0]) * 100000)
        return val, val, currency or "INR"

    # Handle standard numbers or k suffix (e.g. $80k - $120k or 80,000 - 120,000)
    numbers = []
    for part in re.findall(r"(\d+(?:,\d+)*(?:\.\d+)?)\s*(k|K)?", text):
        raw_num, k_suffix = part
        cleaned = raw_num.replace(",", "")
        try:
            val = float(cleaned)
            if k_suffix:
                val *= 1000
            numbers.append(int(val))
        except ValueError:
            continue

    if len(numbers) >= 2:
        return min(numbers[0], numbers[1]), max(numbers[0], numbers[1]), currency
    elif len(numbers) == 1:
        return numbers[0], numbers[0], currency

    return None, None, ""


class RemotiveJobSource(JobSource):
    name = "remotive"
    BASE_URL = "https://remotive.com/api/remote-jobs"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    )
    def _fetch_title(self, title: str) -> List[dict]:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(self.BASE_URL, params={"search": title})
            resp.raise_for_status()
            data = resp.json()
            return data.get("jobs", [])

    def fetch(self, *, titles: List[str], since: Optional[datetime] = None) -> List[JobDTO]:
        results: List[JobDTO] = []
        seen_ids = set()

        for title in titles:
            try:
                raw_jobs = self._fetch_title(title)
            except Exception:
                # If one title fails after retries, continue or bubble
                continue

            for item in raw_jobs:
                ext_id = str(item.get("id"))
                if ext_id in seen_ids:
                    continue
                seen_ids.add(ext_id)

                posted_at = None
                pub_date_str = item.get("publication_date")
                if pub_date_str:
                    try:
                        posted_at = datetime.fromisoformat(pub_date_str)
                        if posted_at.tzinfo is None:
                            posted_at = posted_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        posted_at = None

                if since and posted_at and posted_at < since:
                    continue

                raw_desc = item.get("description", "")
                clean_desc = _clean_html(raw_desc)
                salary_str = item.get("salary", "")
                s_min, s_max, s_curr = _parse_salary(salary_str)

                results.append(
                    JobDTO(
                        source=self.name,
                        external_id=ext_id,
                        title=item.get("title", ""),
                        company=item.get("company_name", ""),
                        location=item.get("candidate_required_location", "Remote"),
                        work_mode="remote",
                        description=clean_desc,
                        apply_url=item.get("url", ""),
                        posted_at=posted_at,
                        salary_min=s_min,
                        salary_max=s_max,
                        salary_currency=s_curr,
                        raw=item,
                    )
                )

        return results
