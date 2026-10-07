"""TCDD Train Transport Provider (EYBİS / TCDD Taşımacılık)."""
import urllib.request
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
from notifyseat.providers.base import BaseProvider
from notifyseat.core.models import TrackingTask, CheckResult, TransportType, ServiceInfo
from notifyseat.core.logger import logger


# Official TCDD YTP Major High-Speed Train (YHT) & Main Corridor Stations
TCDD_STATIONS = [
    # İstanbul YHT İstasyonları
    {"id": "1325", "name": "İstanbul(Söğütlüçeşme)", "city": "İstanbul", "aliases": ["istanbul", "sogutlucesme", "söğütlüçeşme", "kadikoy", "anadolu"]},
    {"id": "992", "name": "İstanbul(Halkalı)", "city": "İstanbul", "aliases": ["halkali", "halkalı", "avrupa"]},
    {"id": "48", "name": "İstanbul(Pendik)", "city": "İstanbul", "aliases": ["pendik"]},
    {"id": "55", "name": "İstanbul(Bostancı)", "city": "İstanbul", "aliases": ["bostanci", "bostancı"]},
    {"id": "20", "name": "İstanbul(Bakırköy)", "city": "İstanbul", "aliases": ["bakirkoy", "bakırköy"]},
    
    # Ankara YHT İstasyonları
    {"id": "98", "name": "Ankara Gar", "city": "Ankara", "aliases": ["ankara", "gar", "baskent", "ankara yht"]},
    {"id": "1306", "name": "Eryaman YHT", "city": "Ankara", "aliases": ["eryaman"]},
    {"id": "76", "name": "Polatlı YHT", "city": "Ankara", "aliases": ["polatli", "polatlı"]},

    # Eskişehir
    {"id": "93", "name": "Eskişehir", "city": "Eskişehir", "aliases": ["eskisehir", "eskişehir", "eskisehir gar"]},

    # Kocaeli & Sakarya
    {"id": "19", "name": "Gebze", "city": "Kocaeli", "aliases": ["gebze"]},
    {"id": "61", "name": "İzmit YHT", "city": "Kocaeli", "aliases": ["izmit", "kocaeli"]},
    {"id": "7", "name": "Arifiye", "city": "Sakarya", "aliases": ["arifiye", "sakarya"]},

    # Bilecik
    {"id": "10", "name": "Bilecik YHT", "city": "Bilecik", "aliases": ["bilecik"]},
    {"id": "14", "name": "Bozüyük YHT", "city": "Bilecik", "aliases": ["bozuyuk", "bozüyük"]},

    # Konya & Karaman
    {"id": "796", "name": "Konya", "city": "Konya", "aliases": ["konya"]},
    {"id": "1336", "name": "Selçuklu YHT (Konya)", "city": "Konya", "aliases": ["selcuklu", "selçuklu"]},
    {"id": "31", "name": "Karaman", "city": "Karaman", "aliases": ["karaman"]},

    # Kırıkkale, Yozgat & Sivas YHT Koridoru
    {"id": "15", "name": "Kırıkkale YHT", "city": "Kırıkkale", "aliases": ["kirikkale", "kırıkkale"]},
    {"id": "52", "name": "Yozgat YHT", "city": "Yozgat", "aliases": ["yozgat"]},
    {"id": "36", "name": "Sivas", "city": "Sivas", "aliases": ["sivas"]},

    # Ege / Ana Hat Bağlantıları
    {"id": "312", "name": "İzmir (Basmane)", "city": "İzmir", "aliases": ["izmir", "basmane"]},
    {"id": "27", "name": "Kütahya", "city": "Kütahya", "aliases": ["kutahya", "kütahya"]}
]

TURKISH_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
ENGLISH_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def normalize_tr(text: str) -> str:
    """Normalize Turkish characters and accents for robust fuzzy matching."""
    if not text:
        return ""
    t = text.replace("İ", "i").replace("I", "i").replace("ı", "i")
    t = t.replace("Ş", "s").replace("ş", "s")
    t = t.replace("Ğ", "g").replace("ğ", "g")
    t = t.replace("Ü", "u").replace("ü", "u")
    t = t.replace("Ö", "o").replace("ö", "o")
    t = t.replace("Ç", "c").replace("ç", "c")
    t = t.lower()
    return "".join(c for c in t if c.isalnum())


def tr_upper(text: str) -> str:
    """Converts Turkish text to uppercase preserving dotted/dotless I correctly."""
    if not text:
        return ""
    return text.replace("i", "İ").replace("ı", "I").upper()


def tcdd_utc_to_local(iso_ts: Any) -> Tuple[str, str]:
    """
    Converts a TCDD UTC timestamp (e.g. '2026-10-10T06:20:00' or epoch ms) into Europe/Istanbul local time (UTC+3).
    Returns (date_str: 'YYYY-MM-DD', time_str: 'HH:MM').
    """
    if not iso_ts:
        return "", ""
    if isinstance(iso_ts, (int, float)):
        try:
            dt = datetime.fromtimestamp(iso_ts / 1000.0, timezone.utc) if iso_ts > 100000000000 else datetime.fromtimestamp(iso_ts, timezone.utc)
            dt_local = dt + timedelta(hours=3)
            return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M")
        except Exception:
            return "", ""

    clean = str(iso_ts).strip().replace("Z", "")
    try:
        if "T" in clean:
            dt = datetime.fromisoformat(clean)
        elif " " in clean:
            dt = datetime.strptime(clean[:19], "%Y-%m-%d %H:%M:%S")
        else:
            return "", clean[:5]
        # TCDD backend stores timestamps in UTC. Turkey is permanently UTC+3.
        dt_local = dt + timedelta(hours=3)
        return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M")
    except Exception:
        return "", clean[:5]


class TCDDProvider(BaseProvider):
    """Integrates with modern TCDD YTP backend & Playwright automation for live seat tracking."""

    BOOKING_URL = "https://ebilet.tcddtasimacilik.gov.tr"
    
    # Modern YTP Cloud & API Endpoints (2026)
    YTP_API_ENDPOINTS = [
        "https://api-yebsp.tcddtasimacilik.gov.tr/train/train-availability",
        "https://api-yebsp.tcddtasimacilik.gov.tr/tms/train/train-availability",
        "https://api-yebsp.tcddtasimacilik.gov.tr/train/load-trains-by-station-and-date",
        "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability",
        "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/load-trains-by-station-and-date"
    ]
    
    # Production JWT token list
    JWT_TOKENS = [
        "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0.eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiMDAzNDI3MmMtNTc2Yi00OTBlLWJhOTgtNTFkMzc1NWNhYjA3IiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidG1zIiwic2Vzc2lvbl9zdGF0ZSI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1tYXN0ZXIiLCJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJvcGVuaWQgZW1haWwgcHJvZmlsZSIsInNpZCI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoid2ViIiwiZ2l2ZW5fbmFtZSI6IiIsImZhbWlseV9uYW1lIjoiIn0.AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg"
    ]
    
    _working_token: Optional[str] = None

    @property
    def transport_type(self) -> TransportType:
        return TransportType.TCDD

    @property
    def name(self) -> str:
        return "TCDD Train (YHT & Mainline)"

    def search_stations(self, query: str) -> List[Dict[str, str]]:
        q_norm = normalize_tr(query)
        matches = []
        for s in TCDD_STATIONS:
            s_norm = normalize_tr(s["name"] + " " + s["city"])
            aliases_norm = [normalize_tr(a) for a in s.get("aliases", [])]
            if q_norm in s_norm or any(q_norm in a for a in aliases_norm):
                matches.append({"id": s["id"], "name": s["name"], "city": s["city"]})
        return matches

    def get_station_by_name(self, name: str) -> Optional[Dict[str, str]]:
        if not name:
            return None
        q_norm = normalize_tr(name)
        # 1. Exact match against station name or alias
        for s in TCDD_STATIONS:
            if q_norm == normalize_tr(s["name"]):
                return s
            if any(q_norm == normalize_tr(a) for a in s.get("aliases", [])):
                return s
        # 2. Substring / partial match
        for s in TCDD_STATIONS:
            s_norm = normalize_tr(s["name"])
            if q_norm in s_norm or s_norm in q_norm:
                return s
            if any(q_norm in normalize_tr(a) or normalize_tr(a) in q_norm for a in s.get("aliases", [])):
                return s
        return None

    def get_popular_routes(self) -> List[Dict[str, str]]:
        return [
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Eskişehir", "label": "İstanbul ➔ Eskişehir (YHT)"},
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Ankara Gar", "label": "İstanbul ➔ Ankara Gar (YHT)"},
            {"origin": "Ankara Gar", "destination": "İstanbul(Söğütlüçeşme)", "label": "Ankara Gar ➔ İstanbul (YHT)"},
            {"origin": "İstanbul(Halkalı)", "destination": "Ankara Gar", "label": "İstanbul (Halkalı) ➔ Ankara Gar (YHT)"},
            {"origin": "Ankara Gar", "destination": "Eskişehir", "label": "Ankara Gar ➔ Eskişehir (YHT)"},
            {"origin": "Ankara Gar", "destination": "Konya", "label": "Ankara Gar ➔ Konya (YHT)"},
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Konya", "label": "İstanbul ➔ Konya (YHT)"},
            {"origin": "Ankara Gar", "destination": "Sivas", "label": "Ankara Gar ➔ Sivas (YHT)"},
            {"origin": "İzmir (Basmane)", "destination": "Eskişehir", "label": "İzmir (Basmane) ➔ Eskişehir (Ege Ekspresi)"}
        ]

    def check_route(self, task: TrackingTask) -> CheckResult:
        """
        Executes an authentic live seat check using the official TCDD YTP backend.
        Never fabricates trains or seat counts.
        """
        import os
        from notifyseat.core.config import ConfigManager

        origin_station = self.get_station_by_name(task.origin)
        dest_station = self.get_station_by_name(task.destination)

        if not origin_station or not dest_station:
            missing = task.origin if not origin_station else task.destination
            return CheckResult(
                task_id=task.id,
                success=False,
                found=False,
                seats_count=0,
                services=[],
                message=f"Station '{missing}' not found in official TCDD station directory."
            )

        origin_name = origin_station["name"]
        dest_name = dest_station["name"]
        origin_id = int(origin_station["id"])
        dest_id = int(dest_station["id"])

        # Check configured tokens from config or environment
        custom_token = os.environ.get("TCDD_TOKEN") or ConfigManager().get().tcdd_token

        # Call live TCDD YTP API
        result = self._check_via_ytp_api(task, origin_name, dest_name, origin_id, dest_id, custom_token=custom_token)
        if result is not None and result.services:
            return result

        # Fallback to timetable + live seat availability query
        scheduled = self.get_scheduled_trains(origin_name, dest_name, task.date)
        if scheduled:
            if task.time_filter:
                scheduled = [s for s in scheduled if self._match_time_filter(s.departure_time, task.time_filter)]
            if scheduled:
                if task.seat_class and task.seat_class != "ANY":
                    for s in scheduled:
                        s.total_available_seats = sum(
                            cnt for c_name, cnt in s.class_breakdown.items()
                            if task.seat_class.lower() in c_name.lower()
                        )

                total_seats = sum(s.total_available_seats for s in scheduled)
                open_services = [s for s in scheduled if s.total_available_seats >= (task.min_seats or 1)]
                found = len(open_services) > 0
                if found:
                    descriptions = [f"{s.total_available_seats} empty seats on {s.departure_time} route" for s in open_services]
                    msg = f"Found {', '.join(descriptions)}."
                else:
                    msg = "All checked routes are sold out."

                return CheckResult(
                    task_id=task.id,
                    success=True,
                    found=found,
                    seats_count=total_seats,
                    services=scheduled,
                    message=msg
                )

        # Failure when API returns no response or route not found
        return CheckResult(
            task_id=task.id,
            success=False,
            found=False,
            seats_count=0,
            services=[],
            message=f"No direct train services found between {origin_name} and {dest_name} on {task.display_date}."
        )

    def _check_via_ytp_api(
        self,
        task: TrackingTask,
        origin_name: str,
        dest_name: str,
        origin_id: int,
        dest_id: int,
        custom_token: Optional[str] = None
    ) -> Optional[CheckResult]:
        """Calls modern YTP API with verified headers and parameters."""
        import requests

        # TCDD expects departure date formatted as (travel_date - 1 day) 21:00:00
        dep_date_str = None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                parsed_d = datetime.strptime(str(task.date).strip(), fmt)
                offset_d = parsed_d - timedelta(days=1)
                dep_date_str = offset_d.strftime("%d-%m-%Y 21:00:00")
                break
            except Exception:
                pass

        if not dep_date_str:
            dep_date_str = str(task.date)

        payload = {
            "searchRoutes": [
                {
                    "departureStationId": origin_id,
                    "departureStationName": tr_upper(origin_name),
                    "arrivalStationId": dest_id,
                    "arrivalStationName": tr_upper(dest_name),
                    "departureDate": dep_date_str
                }
            ],
            "passengerTypeCounts": [
                {
                    "id": 0,
                    "count": task.min_seats or 1
                }
            ],
            "searchReservation": False,
            "searchType": "DOMESTIC",
            "blTrainTypes": ["TURISTIK_TREN"]
        }

        tokens_to_try = []
        if custom_token:
            clean_tok = custom_token.replace("Bearer ", "").strip()
            tokens_to_try.append(clean_tok)
        if self._working_token and self._working_token not in tokens_to_try:
            tokens_to_try.append(self._working_token)
        for tok in self.JWT_TOKENS:
            if tok not in tokens_to_try:
                tokens_to_try.append(tok)

        endpoints = [
            "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1",
            "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability",
            "https://api-yebsp.tcddtasimacilik.gov.tr/train/train-availability"
        ]

        for token in tokens_to_try:
            headers = {
                "Host": "web-api-prod-ytp.tcddtasimacilik.gov.tr",
                "Connection": "keep-alive",
                "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "unit-id": "3895",
                "sec-ch-ua-mobile": "?0",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Authorization": token,
                "sec-ch-ua-platform": '"Windows"',
                "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
                "Referer": "https://ebilet.tcddtasimacilik.gov.tr/",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
            }

            for endpoint in endpoints:
                try:
                    r = requests.post(endpoint, json=payload, headers=headers, timeout=12)
                    if r.status_code == 200:
                        data = r.json()
                        if isinstance(data, (list, dict)) and data:
                            parsed = self._parse_ytp_response(task, data, origin_name, dest_name)
                            if parsed is not None:
                                self._working_token = token
                                return parsed
                    elif r.status_code == 429:
                        logger.warning("TCDD sunucusu istek sınırına (rate limit) ulaşıldığını bildirdi.")
                        return CheckResult(
                            task_id=task.id,
                            success=False,
                            found=False,
                            seats_count=0,
                            rate_limited=True,
                            backoff_seconds=180,
                            message="TCDD sunucuları kısa süreli yoğunluk nedeniyle yavaşlamamızı istedi. IP adresinizi korumak için kontrolleri 3 dakika mola vererek otomatik devam ettireceğiz."
                        )
                    elif r.status_code == 403:
                        logger.debug(f"YTP API 403 on {endpoint}")
                except Exception as e:
                    logger.debug(f"YTP API probe error on {endpoint}: {e}")
                    continue

        return None

    def _parse_ytp_response(self, task: TrackingTask, data: Any, origin_name: str, dest_name: str) -> CheckResult:
        """Parses TCDD JSON response (including modern trainLegs structure) and extracts all trips, times, and seats."""
        services: List[ServiceInfo] = []
        total_seats = 0

        # Handle modern trainLegs structure
        if isinstance(data, dict) and "trainLegs" in data:
            for leg in data.get("trainLegs", []):
                for avail in leg.get("trainAvailabilities", []):
                    for train in avail.get("trains", []):
                        train_name = train.get("commercialName") or train.get("name") or f"YHT {train.get('number', '')}"
                        train_num = str(train.get("number") or train.get("id", ""))
                        
                        # Extract departure / arrival from segments (timestamps in ms)
                        dep_time = ""
                        arr_time = ""
                        segments = train.get("segments", [])
                        if segments:
                            dep_ts = segments[0].get("departureTime")
                            arr_ts = segments[-1].get("arrivalTime")
                            if dep_ts:
                                dep_dt = datetime.fromtimestamp(dep_ts / 1000.0) if dep_ts > 100000000000 else datetime.fromtimestamp(dep_ts)
                                dep_time = dep_dt.strftime("%H:%M")
                            if arr_ts:
                                arr_dt = datetime.fromtimestamp(arr_ts / 1000.0) if arr_ts > 100000000000 else datetime.fromtimestamp(arr_ts)
                                arr_time = arr_dt.strftime("%H:%M")
                        
                        if not dep_time:
                            dep_time = train.get("departureTime", "")

                        # Filter by time if requested
                        if task.time_filter and not self._match_time_filter(dep_time, task.time_filter):
                            continue

                        # Extract minPrice (base fare or cabin fare)
                        min_price_obj = train.get("minPrice") or {}
                        price_amount = float(min_price_obj.get("priceAmount", 0.0) or 0.0)
                        price_currency = min_price_obj.get("priceCurrency") or "TRY"

                        # Fallback to fare info if minPrice is not present at train level
                        if price_amount <= 0:
                            for fare in train.get("availableFareInfo", []):
                                p = float(fare.get("fare", 0.0) or 0.0)
                                if p > 0:
                                    price_amount = p
                                    break

                        # Extract exact available seats per class and carriage/araba
                        class_breakdown = {}
                        car_breakdown = []
                        train_seats = 0

                        fare_infos = train.get("availableFareInfo", [])
                        if fare_infos:
                            for fare in fare_infos:
                                car_raw = fare.get("name") or (fare.get("trainCar") or {}).get("name") or fare.get("trainCarName") or fare.get("carNo") or fare.get("wagonNo")
                                if not car_raw and fare.get("carIndex") is not None:
                                    try:
                                        car_raw = str(int(fare.get("carIndex")) + 1)
                                    except Exception:
                                        pass
                                car_label = f"{car_raw}. Araba" if car_raw and str(car_raw).strip().isdigit() else (f"{car_raw}" if car_raw else "")

                                c_list = fare.get("cabinClasses") or fare.get("availabilities") or []
                                for c_info in c_list:
                                    c_name_raw = (c_info.get("cabinClass") or {}).get("name", "")
                                    c_name_upper = c_name_raw.upper()
                                    if "BUSİNESS" in c_name_upper or "BUSINESS" in c_name_upper:
                                        c_name = "Business"
                                    elif "EKONOMİ" in c_name_upper or "EKONOMI" in c_name_upper or "PULMAN" in c_name_upper:
                                        c_name = "Ekonomi"
                                    else:
                                        # Only Business and Ekonomi are considered per Ayberk's requirement
                                        continue

                                    count = int(c_info.get("availabilityCount", 0) or c_info.get("availability", 0) or 0)
                                    if count > 0:
                                        if task.seat_class and task.seat_class != "ANY":
                                            if task.seat_class.lower() not in c_name.lower():
                                                continue
                                        class_breakdown[c_name] = class_breakdown.get(c_name, 0) + count
                                        car_breakdown.append({
                                            "class": c_name,
                                            "car": car_label,
                                            "count": count
                                        })
                                        train_seats += count
                        else:
                            for c_info in train.get("cabinClassAvailabilities", []):
                                c_name_raw = (c_info.get("cabinClass") or {}).get("name", "")
                                car_raw = c_info.get("trainCarName") or (c_info.get("trainCar") or {}).get("name") or c_info.get("name") or c_info.get("carNo") or c_info.get("wagonNo")
                                if not car_raw and c_info.get("carIndex") is not None:
                                    try:
                                        car_raw = str(int(c_info.get("carIndex")) + 1)
                                    except Exception:
                                        pass
                                car_label = f"{car_raw}. Araba" if car_raw and str(car_raw).strip().isdigit() else (f"{car_raw}" if car_raw else "")
                                c_name_upper = c_name_raw.upper()
                                if "BUSİNESS" in c_name_upper or "BUSINESS" in c_name_upper:
                                    c_name = "Business"
                                elif "EKONOMİ" in c_name_upper or "EKONOMI" in c_name_upper or "PULMAN" in c_name_upper:
                                    c_name = "Ekonomi"
                                else:
                                    # Only Business and Ekonomi are considered per Ayberk's requirement
                                    continue

                                count = int(c_info.get("availabilityCount", 0) or c_info.get("availability", 0) or 0)
                                if count > 0:
                                    if task.seat_class and task.seat_class != "ANY":
                                        if task.seat_class.lower() not in c_name.lower():
                                            continue
                                    class_breakdown[c_name] = class_breakdown.get(c_name, 0) + count
                                    car_breakdown.append({
                                        "class": c_name,
                                        "car": car_label,
                                        "count": count
                                    })
                                    train_seats += count

                        services.append(ServiceInfo(
                            service_id=train_num,
                            service_name=f"{train_num} - {train_name}",
                            departure_time=dep_time,
                            arrival_time=arr_time,
                            origin=origin_name,
                            destination=dest_name,
                            date=task.date,
                            total_available_seats=train_seats,
                            class_breakdown=class_breakdown,
                            car_breakdown=car_breakdown,
                            price=price_amount if price_amount > 0 else None,
                            currency=price_currency,
                            booking_url=self.BOOKING_URL,
                            operator="TCDD Taşımacılık",
                            notes=f"Available seats on {dep_time} route" if train_seats > 0 else "Sold Out"
                        ))
                        total_seats += train_seats

            found = total_seats >= task.min_seats
            open_services = [s for s in services if s.total_available_seats > 0]
            if found and open_services:
                descriptions = [f"{s.total_available_seats} empty seats on {s.departure_time} route" for s in open_services]
                msg = f"Found {', '.join(descriptions)}."
            else:
                msg = "All checked routes are sold out."

            return CheckResult(
                task_id=task.id,
                success=True,
                found=found,
                seats_count=total_seats,
                services=services,
                message=msg
            )

        if isinstance(data, list):
            sefer_list = data
        else:
            sefer_list = (
                data.get("trainAvailabilityList", []) or
                data.get("trains", []) or
                data.get("seferListesi", []) or 
                data.get("cevapBilgileri", {}).get("seferListesi", []) or
                data.get("seferSorgulamaSonucList", [])
            )

        checked_trains_summary = []

        for sefer in sefer_list:
            train_name = sefer.get("trainName") or sefer.get("trenAdi") or sefer.get("seferAdi") or f"YHT {sefer.get('trainId', sefer.get('trenNo', ''))}"
            dep_time = sefer.get("departureTime") or sefer.get("binisSaati") or sefer.get("kalkisSaati", "")
            arr_time = sefer.get("arrivalTime") or sefer.get("inisSaati") or sefer.get("varisSaati", "")

            # Filter by time if requested
            if task.time_filter and not self._match_time_filter(dep_time, task.time_filter):
                continue

            # Parse wagons and seat availability
            vagon_tipleri = (
                sefer.get("wagons", []) or 
                sefer.get("cabinClasses", []) or
                sefer.get("vagonTipleriBosYerUcret", []) or 
                sefer.get("vagonListesi", []) or
                sefer.get("vagonTipiBosYerList", [])
            )
            class_breakdown = {}
            train_seats = 0

            for vagon in vagon_tipleri:
                tip = vagon.get("name") or vagon.get("cabinClassName") or vagon.get("vagonTipAdi") or vagon.get("vagonTipi", "Pulman")
                bos_yer = int(vagon.get("availableSeats", 0) or vagon.get("seatCount", 0) or vagon.get("bosYer", 0) or vagon.get("kalanKoltukSayisi", 0))
                
                # Check class filter
                if task.seat_class and task.seat_class != "ANY":
                    if task.seat_class.lower() not in tip.lower():
                        continue

                class_breakdown[tip] = bos_yer
                train_seats += bos_yer

            checked_trains_summary.append(f"{dep_time} ({train_seats} seats)")

            services.append(ServiceInfo(
                service_id=str(sefer.get("seferId") or sefer.get("trenNo", "")),
                service_name=train_name,
                departure_time=dep_time,
                arrival_time=arr_time,
                origin=origin_name,
                destination=dest_name,
                date=task.date,
                total_available_seats=train_seats,
                class_breakdown=class_breakdown,
                booking_url=self.BOOKING_URL,
                operator="TCDD Taşımacılık",
                notes=f"Found {train_seats} empty seats on {dep_time} route from {origin_name} to {dest_name}" if train_seats > 0 else "Sold Out"
            ))
            total_seats += train_seats

        found = total_seats >= task.min_seats
        
        if found:
            # Build clear, explicit message requested by Ayberk
            trip_descriptions = []
            for s in services:
                breakdown = ", ".join([f"{count} {cls_name}" for cls_name, count in s.class_breakdown.items() if count > 0])
                trip_descriptions.append(f"found {s.total_available_seats} empty seats on {s.departure_time} route ({breakdown})")
            
            detail_msg = "; ".join(trip_descriptions)
            msg = f"🎉 {detail_msg} from {origin_name} to {dest_name} on {task.display_date}."
        else:
            if checked_trains_summary:
                msg = f"Checked {len(checked_trains_summary)} trains on {task.display_date} [{', '.join(checked_trains_summary[:4])}]: All Sold Out (0 seats). Monitoring for cancellations..."
            else:
                msg = f"No scheduled trains found between {origin_name} and {dest_name} on {task.display_date}."

        return CheckResult(
            task_id=task.id,
            success=True,
            found=found,
            seats_count=total_seats,
            services=services,
            message=msg
        )

    def get_trains_by_station_and_date(self, station_id: int, date_str: str) -> List[Dict[str, Any]]:
        """Queries TCDD load-trains-by-station-and-date endpoint for all scheduled trains passing through station."""
        import requests
        from notifyseat.core.config import ConfigManager

        iso_date = str(date_str).strip()
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                iso_date = datetime.strptime(str(date_str).strip(), fmt).strftime("%Y-%m-%d")
                break
            except Exception:
                pass

        url = "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/load-trains-by-station-and-date"
        headers = {
            "Host": "web-api-prod-ytp.tcddtasimacilik.gov.tr",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "unit-id": "3895",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Authorization": self.JWT_TOKENS[0],
            "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
            "Referer": "https://ebilet.tcddtasimacilik.gov.tr/"
        }
        cfg = ConfigManager().get()
        if hasattr(cfg, "tcdd_token") and cfg.tcdd_token:
            headers["Authorization"] = cfg.tcdd_token

        try:
            r = requests.post(url, json={"stationId": station_id, "date": iso_date}, headers=headers, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.debug(f"Failed to load trains for station {station_id}: {e}")
        return []

    def get_seat_availability_for_train(
        self,
        train_id: int,
        from_station_id: int,
        to_station_id: int
    ) -> Tuple[int, Dict[str, int], List[Dict[str, Any]], Optional[float], str]:
        """
        Queries official TCDD /tms/seat-maps/load-by-train-id endpoint to fetch real-time
        available seat counts, cabin class breakdown, wagon/car details, and min price.
        Returns: (total_seats, class_breakdown, car_breakdown, min_price, currency)
        """
        import requests
        from notifyseat.core.config import ConfigManager

        headers = {
            "Host": "web-api-prod-ytp.tcddtasimacilik.gov.tr",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "unit-id": "3895",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Authorization": self.JWT_TOKENS[0],
            "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
            "Referer": "https://ebilet.tcddtasimacilik.gov.tr/"
        }
        cfg = ConfigManager().get()
        if hasattr(cfg, "tcdd_token") and cfg.tcdd_token:
            headers["Authorization"] = cfg.tcdd_token

        payload = {
            "trainId": train_id,
            "fromStationId": from_station_id,
            "toStationId": to_station_id
        }

        total_seats = 0
        class_bd: Dict[str, int] = {}
        car_bd: List[Dict[str, Any]] = []
        min_price: Optional[float] = None
        curr = "TRY"

        try:
            r = requests.post(
                "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/seat-maps/load-by-train-id",
                json=payload,
                headers=headers,
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                for sm in data.get("seatMaps", []):
                    c_info = sm.get("seatMapTemplate", {}).get("car", {})
                    car_name = c_info.get("name", "")
                    raw_count = int(sm.get("availableSeatCount", 0) or 0)

                    allocated_seats = {
                        s.get("seatNumber")
                        for s in sm.get("allocationSeats", [])
                        if s.get("seatNumber")
                    }
                    seat_prices = sm.get("seatPrices", [])

                    if seat_prices:
                        seat_map_by_num = {}
                        for sp in seat_prices:
                            num = sp.get("seatNumber")
                            if num and num not in seat_map_by_num:
                                seat_map_by_num[num] = sp

                        free_seats = [
                            sp for num, sp in seat_map_by_num.items()
                            if num not in allocated_seats
                        ]
                        normal_free = [
                            s for s in free_seats
                            if s.get("cabinClassId") not in (12, 13)
                            and not str(s.get("seatNumber", "")).endswith("H")
                            and "ENGELL" not in str(s.get("seatNumber", "")).upper()
                        ]
                        count = len(normal_free)
                    else:
                        count = raw_count

                    cls_name_raw = (sm.get("cabinClass") or {}).get("name") or sm.get("seatMapTemplate", {}).get("name", "")
                    c_upper = cls_name_raw.upper()
                    if "BUSİNESS" in c_upper or "BUSINESS" in c_upper:
                        c_name = "Business"
                    elif "EKONOMİ" in c_upper or "EKONOMI" in c_upper or "PULMAN" in c_upper:
                        c_name = "Ekonomi"
                    else:
                        c_name = "Ekonomi"

                    if count > 0:
                        class_bd[c_name] = class_bd.get(c_name, 0) + count
                        total_seats += count
                        car_bd.append({
                            "class": c_name,
                            "car": car_name,
                            "count": count
                        })

                    # Track min price
                    sm_min = sm.get("minPrice")
                    if isinstance(sm_min, dict):
                        p_val = float(sm_min.get("priceAmount", 0.0) or 0.0)
                        if p_val > 0:
                            min_price = min(min_price, p_val) if min_price else p_val
                            curr = sm_min.get("priceCurrency") or curr

                    for sp in seat_prices:
                        p_raw = sp.get("price")
                        if isinstance(p_raw, dict):
                            p = float(p_raw.get("priceAmount", 0.0) or 0.0)
                            if p > 0:
                                min_price = min(min_price, p) if min_price else p
                                curr = p_raw.get("priceCurrency") or curr
                        elif isinstance(p_raw, (int, float)):
                            p = float(p_raw)
                            if p > 0:
                                min_price = min(min_price, p) if min_price else p

        except Exception as e:
            logger.debug(f"Seat map fetch failed for train {train_id}: {e}")

        return total_seats, class_bd, car_bd, min_price, curr

    def get_scheduled_trains(self, origin: str, destination: str, date: str) -> List[ServiceInfo]:
        """Fetches all scheduled train services for a given route and date using TCDD official timetable."""
        origin_station = self.get_station_by_name(origin)
        dest_station = self.get_station_by_name(destination)
        if not origin_station or not dest_station:
            return []

        # 1. Try checking via live availability API if working token is cached
        if self._working_token:
            temp_task = TrackingTask(
                origin=origin,
                destination=destination,
                date=date,
                time_filter=None,
                min_seats=1
            )
            avail_res = self._check_via_ytp_api(
                temp_task,
                origin_station["name"],
                dest_station["name"],
                int(origin_station["id"]),
                int(dest_station["id"])
            )
            if avail_res and avail_res.services:
                return sorted(avail_res.services, key=lambda s: s.departure_time or "")

        # 2. Query timetable directly via /tms/train/load-trains-by-station-and-date
        orig_id = int(origin_station["id"])
        dest_id = int(dest_station["id"])
        trains_orig = self.get_trains_by_station_and_date(orig_id, date)
        trains_dest = self.get_trains_by_station_and_date(dest_id, date)

        dest_map = {t["trainNumber"]: t for t in trains_dest if "trainNumber" in t}
        dest_name_clean = normalize_tr(dest_station["name"])

        candidate_items = []
        seen_train_nums = set()

        for t in trains_orig:
            t_num = str(t.get("trainNumber") or t.get("trainId") or "").strip()
            if not t_num or t_num in seen_train_nums:
                continue

            # Skip trains terminating at origin or originating at destination
            if t.get("lineEndStationId") == orig_id or t.get("lineStartStationId") == dest_id:
                continue

            orig_is_start = (t.get("stationInfo") == "departure_station" or t.get("lineStartStationId") == orig_id)
            if orig_is_start:
                dep_raw = t.get("tsDepartureTime") or t.get("lineStartDepartureTime")
            else:
                dep_raw = t.get("tsArrivalTime") or t.get("tsDepartureTime")

            _, dep_time = tcdd_utc_to_local(dep_raw)

            arr_time = ""
            matched = False

            # Check if train appears at destination with valid sequence
            if t_num in dest_map:
                dt = dest_map[t_num]
                arr_raw = dt.get("tsArrivalTime") or dt.get("lineEndArrivalTime")
                if dep_raw and arr_raw:
                    _, arr_t_val = tcdd_utc_to_local(arr_raw)
                    if arr_raw <= dep_raw and t.get("lineEndStationId") != dest_id:
                        continue
                    matched = True
                    arr_time = arr_t_val

            # Or train terminates directly at destination station
            if not matched and t.get("lineEndStationId") == dest_id:
                matched = True
                arr_raw = t.get("lineEndArrivalTime") or t.get("tsArrivalTime")
                _, arr_time = tcdd_utc_to_local(arr_raw)

            # Or line name explicitly indicates travel towards destination
            if not matched and dest_name_clean in normalize_tr(t.get("lineName") or ""):
                matched = True
                arr_raw = t.get("lineEndArrivalTime") or t.get("tsArrivalTime")
                _, arr_time = tcdd_utc_to_local(arr_raw)

            if matched:
                seen_train_nums.add(t_num)
                candidate_items.append((t, t_num, dep_time, arr_time))

        services: List[ServiceInfo] = []
        if candidate_items:
            from concurrent.futures import ThreadPoolExecutor

            def _fetch_candidate_seats(item):
                t_obj, t_num_val, dep_t_val, arr_t_val = item
                train_id = t_obj.get("trainId")
                if train_id:
                    tot, cls_bd, car_bd, min_p, curr = self.get_seat_availability_for_train(
                        int(train_id), orig_id, dest_id
                    )
                else:
                    tot, cls_bd, car_bd, min_p, curr = 0, {}, [], None, "TRY"
                return (item, tot, cls_bd, car_bd, min_p, curr)

            workers = min(len(candidate_items), 8)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                results = list(executor.map(_fetch_candidate_seats, candidate_items))

            for item, tot, cls_bd, car_bd, min_p, curr in results:
                t_obj, t_num_val, dep_t_val, arr_t_val = item
                train_name = t_obj.get("trainName") or f"YHT {t_num_val}"
                services.append(ServiceInfo(
                    service_id=t_num_val,
                    service_name=train_name,
                    departure_time=dep_t_val,
                    arrival_time=arr_t_val,
                    origin=origin_station["name"],
                    destination=dest_station["name"],
                    date=date,
                    total_available_seats=tot,
                    class_breakdown=cls_bd,
                    car_breakdown=car_bd,
                    price=min_p,
                    currency=curr,
                    booking_url=self.BOOKING_URL,
                    operator="TCDD Taşımacılık",
                    notes=f"Available seats on {dep_t_val} route" if tot > 0 else "Sold Out"
                ))

        return sorted(services, key=lambda s: s.departure_time or "")

    def _match_time_filter(self, dep_time: str, filter_str: str) -> bool:
        if not dep_time or not filter_str:
            return True
        filter_str = filter_str.strip()

        # Comma-separated exact times or list, e.g. "05:30, 07:20, 11:10"
        if "," in filter_str:
            times = [t.strip() for t in filter_str.split(",") if t.strip()]
            return any(t == dep_time or t in dep_time for t in times)

        # Exact hour match e.g. "16:35"
        if ":" in filter_str and "-" not in filter_str:
            return filter_str == dep_time or filter_str in dep_time

        # Range match e.g. "08:00-14:00"
        if "-" in filter_str:
            try:
                start_s, end_s = filter_str.split("-")
                dep_h = int(dep_time.split(":")[0])
                start_h = int(start_s.split(":")[0])
                end_h = int(end_s.split(":")[0])
                return start_h <= dep_h <= end_h
            except Exception:
                return True

        # Named ranges
        dep_h = int(dep_time.split(":")[0]) if ":" in dep_time else 0
        if filter_str.lower() == "morning":
            return 5 <= dep_h < 12
        elif filter_str.lower() == "afternoon":
            return 12 <= dep_h < 18
        elif filter_str.lower() == "evening":
            return 18 <= dep_h < 24

        return True
