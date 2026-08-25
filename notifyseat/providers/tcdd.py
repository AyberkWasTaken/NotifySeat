"""TCDD Train Transport Provider (EYBİS / TCDD Taşımacılık)."""
import urllib.request
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
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
        "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0.eyJleHAiOjE3MzE5MzA5OTcsImlhdCI6MTczMTkzMDkzNywianRpIjoiMzI3NzczN2QtN2E1Mi00MzBiLWJkY2EtNWIxNWE2ODE2NGY3IiwiaXNzIjoiaHR0cDovL3VhdC1yYWlsLmRpdHJhdm8uY29tOjgwODAvcmVhbG1zL21hc3RlciIsImF1ZCI6ImFjY291bnQiLCJzdWIiOiIwMDM0MjcyYy01NzZiLTQ5MGUtYmE5OC01MWQzNzU1Y2FiMDciLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJ0bXMiLCJzZXNzaW9uX3N0YXRlIjoiYzVmODc1YjctNDE3MS00MjY1LTg3YzMtMzU3NTRmYmM2NTY2IiwiYWNyIjoiMSIsInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJkZWZhdWx0LXJvbGVzLW1hc3RlciIsIm9mZmxpbmVfYWNjZXNzIiwidW1hX2F1dGhvcml6YXRpb24iXX0sInJlc291cmNlX2FjY2VzcyI6eyJhY2NvdW50Ijp7InJvbGVzIjpbIm1hbmFnZS1hY2NvdW50IiwibWFuYWdlLWFjY291bnQtbGlua3MiLCJ2aWV3LXByb2ZpbGUiXX19LCJzY29wZSI6Im9wZW5pZCBlbWFpbCBwcm9maWxlIiwic2lkIjoiYzVmODc1YjctNDE3MS00MjY1LTg3YzMtMzU3NTRmYmM2NTY2IiwiZW1haWxfdmVyaWZpZWQiOmZhbHNlLCJwcmVmZXJyZWRfdXNlcm5hbWUiOiJ3ZWIiLCJnaXZlbl9uYW1lIjoiIiwiZmFtaWx5X25hbWUiOiIifQ.IxX21XVcRltIDzyjHXlvME1QpKyYM6sI-GxGXlyD7qklr-424MY5DHRRe8JXlY1F5qsI607DQV146MACYuAUXN8jtrfZD2NcK_0QsGis5IA_rue9cVvcvzia-NTV3Ka2B285DpVjOMdFTcsDtxZLRZ0tD6w0A_WzW1KId1lvLsY08UHq6WKvlaDVoa3w3LKC8nDwPSvSMIBWhBpG_5-rxbbf8tpoAfsbJHXVjeOARx5gg713FBwAWzyWrp72SMVozyuwboQrPo4xhPEkwn_V_Ecyp45G3Xe4QOEZpDtbi25fup6xyM4gRq73TCczaErtrP1EQbWgefSgBemldOYLGg",
        "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJlVFFicDhDMmpiakp1cnUzQVk2a0ZnV196U29MQXZIMmJ5bTJ2OUg5THhRIn0.eyJleHAiOjE3MjEzODQ0NzAsImlhdCI6MTcyMTM4NDQxMCwianRpIjoiYWFlNjVkNzgtNmRkZS00ZGY4LWEwZWYtYjRkNzZiYjZlODNjIiwiaXNzIjoiaHR0cDovL3l0cC1wcm9kLW1hc3RlcjEudGNkZHRhc2ltYWNpbGlrLmdvdi50cjo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJhY2NvdW50Iiwic3ViIjoiMDAzNDI3MmMtNTc2Yi00OTBlLWJhOTgtNTFkMzc1NWNhYjA3IiwidHlwIjoiQmVhcmVyIiwiYXpwIjoidG1zIiwic2Vzc2lvbl9zdGF0ZSI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImFjciI6IjEiLCJyZWFsbV9hY2Nlc3MiOnsicm9sZXMiOlsiZGVmYXVsdC1yb2xlcy1tYXN0ZXIiLCJvZmZsaW5lX2FjY2VzcyIsInVtYV9hdXRob3JpemF0aW9uIl19LCJyZXNvdXJjZV9hY2Nlc3MiOnsiYWNjb3VudCI6eyJyb2xlcyI6WyJtYW5hZ2UtYWNjb3VudCIsIm1hbmFnZS1hY2NvdW50LWxpbmtzIiwidmlldy1wcm9maWxlIl19fSwic2NvcGUiOiJvcGVuaWQgZW1haWwgcHJvZmlsZSIsInNpZCI6IjAwYzM4NTJiLTg1YjEtNDMxNS04OGIwLWQ0MWMxMTcyYzA0MSIsImVtYWlsX3ZlcmlmaWVkIjpmYWxzZSwicHJlZmVycmVkX3VzZXJuYW1lIjoid2ViIiwiZ2l2ZW5fbmFtZSI6IiIsImZhbWlseV9uYW1lIjoiIn0.AIW_4Qws2wfwxyVg8dgHRT9jB3qNavob2C4mEQIQGl3urzW2jALPx-e51ZwHUb-TXB-X2RPHakonxKnWG6tDIP5aKhiidzXDcr6pDDoYU5DnQhMg1kywyOaMXsjLFjuYN5PAyGUMh6YSOVsg1PzNh-5GrJF44pS47JnB9zk03Pr08napjsZPoRB-5N4GQ49cnx7ePC82Y7YIc-gTew2baqKQPz9_v381Gbm2V38PZDH9KldlcWut7kqQYJFMJ7dkM_entPJn9lFk7R5h5j_06OlQEpWRMQTn9SQ1AYxxmZxBu5XYMKDkn4rzIIVCkdTPJNCt5PvjENjClKFeUA1DOg"
    ]

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
        if result is not None:
            return result

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

        tokens_to_try = list(self.JWT_TOKENS)
        if custom_token:
            clean_tok = custom_token.replace("Bearer ", "").strip()
            if clean_tok not in tokens_to_try:
                tokens_to_try.append(clean_tok)

        endpoints = [
            "https://web-api-prod-ytp.tcddtasimacilik.gov.tr/tms/train/train-availability?environment=dev&userId=1"
        ]

        for token in tokens_to_try:
            headers = {
                "Host": "web-api-prod-ytp.tcddtasimacilik.gov.tr",
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:154.0) Gecko/20100101 Firefox/154.0",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "tr",
                "Authorization": token,
                "Content-Type": "application/json",
                "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Sec-GPC": "1",
                "unit-id": "3895"
            }

            for endpoint in endpoints:
                try:
                    r = requests.post(endpoint, json=payload, headers=headers, timeout=8)
                    if r.status_code == 200:
                        data = r.json()
                        if isinstance(data, (list, dict)) and data:
                            parsed = self._parse_ytp_response(task, data, origin_name, dest_name)
                            if parsed is not None:
                                return parsed
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
                descriptions = [f"found {s.total_available_seats} empty seats on {s.departure_time} route ({', '.join([f'{cnt} {cls}' for cls, cnt in s.class_breakdown.items() if cnt > 0])})" for s in open_services]
                msg = f"🎉 {'; '.join(descriptions)} from {origin_name} to {dest_name} on {task.date}."
            else:
                msg = f"TCDD Live Check ({origin_name} ➔ {dest_name} on {task.date}): All checked routes are Sold Out. Monitoring for cancellations..."

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

            if train_seats > 0:
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
                    notes=f"Found {train_seats} empty seats on {dep_time} route from {origin_name} to {dest_name}"
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

    def get_scheduled_trains(self, origin: str, destination: str, date: str) -> List[ServiceInfo]:
        """Fetches all scheduled train services for a given route and date."""
        temp_task = TrackingTask(
            origin=origin,
            destination=destination,
            date=date,
            time_filter=None,
            min_seats=1
        )
        res = self.check_route(temp_task)
        if res and res.services:
            return sorted(res.services, key=lambda s: s.departure_time or "")
        return []

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
