"""TCDD Train Transport Provider (EYBİS / TCDD Taşımacılık)."""
import urllib.request
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from notifyseat.providers.base import BaseProvider
from notifyseat.core.models import TrackingTask, CheckResult, TransportType, ServiceInfo
from notifyseat.core.logger import logger


TCDD_STATIONS = [
    {"id": "60", "name": "İstanbul(Söğütlüçeşme)", "city": "İstanbul", "aliases": ["istanbul", "sogutlucesme", "kadikoy", "anadolu"]},
    {"id": "23", "name": "İstanbul(Halkalı)", "city": "İstanbul", "aliases": ["halkali", "avrupa"]},
    {"id": "58", "name": "İstanbul(Pendik)", "city": "İstanbul", "aliases": ["pendik"]},
    {"id": "55", "name": "İstanbul(Bostancı)", "city": "İstanbul", "aliases": ["bostanci"]},
    {"id": "20", "name": "İstanbul(Bakırköy)", "city": "İstanbul", "aliases": ["bakirkoy"]},
    {"id": "2", "name": "Ankara Gar", "city": "Ankara", "aliases": ["ankara", "gar", "baskent"]},
    {"id": "592", "name": "Eryaman YHT", "city": "Ankara", "aliases": ["eryaman"]},
    {"id": "14", "name": "Eskişehir", "city": "Eskişehir", "aliases": ["eskisehir", "eskişehir"]},
    {"id": "26", "name": "Konya", "city": "Konya", "aliases": ["konya"]},
    {"id": "40", "name": "Konya(Selçuklu YHT)", "city": "Konya", "aliases": ["selcuklu"]},
    {"id": "31", "name": "Karaman", "city": "Karaman", "aliases": ["karaman"]},
    {"id": "36", "name": "Sivas", "city": "Sivas", "aliases": ["sivas"]},
    {"id": "52", "name": "Yozgat YHT", "city": "Yozgat", "aliases": ["yozgat"]},
    {"id": "4", "name": "İzmir(Basmane)", "city": "İzmir", "aliases": ["izmir", "basmane"]},
    {"id": "5", "name": "İzmir(Alsancak)", "city": "İzmir", "aliases": ["alsancak"]},
    {"id": "1", "name": "Adana", "city": "Adana", "aliases": ["adana"]},
    {"id": "10", "name": "Bilecik YHT", "city": "Bilecik", "aliases": ["bilecik"]},
    {"id": "18", "name": "Kayseri", "city": "Kayseri", "aliases": ["kayseri"]},
    {"id": "32", "name": "Kars", "city": "Kars", "aliases": ["kars"]},
    {"id": "15", "name": "Kırıkkale YHT", "city": "Kırıkkale", "aliases": ["kirikkale"]},
    {"id": "61", "name": "İzmit YHT", "city": "Kocaeli", "aliases": ["izmit", "kocaeli"]},
    {"id": "19", "name": "Gebze", "city": "Kocaeli", "aliases": ["gebze"]},
    {"id": "7", "name": "Arifiye", "city": "Sakarya", "aliases": ["arifiye", "sakarya", "adapazari"]},
    {"id": "27", "name": "Kütahya", "city": "Kütahya", "aliases": ["kutahya"]},
    {"id": "3", "name": "Afyon A.Çetinkaya", "city": "Afyonkarahisar", "aliases": ["afyon"]},
    {"id": "13", "name": "Denizli", "city": "Denizli", "aliases": ["denizli"]},
    {"id": "28", "name": "Malatya", "city": "Malatya", "aliases": ["malatya"]},
    {"id": "12", "name": "Diyarbakır", "city": "Diyarbakır", "aliases": ["diyarbakir"]},
    {"id": "16", "name": "Gaziantep", "city": "Gaziantep", "aliases": ["gaziantep"]}
]

TURKISH_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
ENGLISH_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def normalize_tr(text: str) -> str:
    """Normalize Turkish characters for fuzzy matching."""
    t = text.lower().strip()
    tr_map = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")
    return t.translate(tr_map).replace(" ", "").replace("(", "").replace(")", "").replace("-", "")


class TCDDProvider(BaseProvider):
    """Integrates directly with TCDD EYBİS backend for live seat tracking."""

    ENDPOINTS = [
        "https://api-yebsp.tcddtasimacilik.gov.tr/sefer/seferSorgula",
        "https://eybistrm.tcdd.gov.tr/WebServisWeb/rest/EybisRestApplication/seferSorgula"
    ]
    BOOKING_URL = "https://ebilet.tcddtasimacilik.gov.tr"

    HEADERS = {
        "Authorization": "Basic ZGl0cmF2b3llYnNwOmRpdHJhMzQhdm8u",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
        "Referer": "https://ebilet.tcddtasimacilik.gov.tr/",
        "Accept": "application/json, text/plain, */*"
    }

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
        q_norm = normalize_tr(name)
        for s in TCDD_STATIONS:
            s_norm = normalize_tr(s["name"])
            if q_norm == s_norm or s_norm in q_norm or q_norm in s_norm:
                return s
            if any(q_norm == normalize_tr(a) for a in s.get("aliases", [])):
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
            {"origin": "İzmir(Basmane)", "destination": "Eskişehir", "label": "İzmir (Basmane) ➔ Eskişehir (Ege Ekspresi)"}
        ]

    def _format_dates(self, date_str: str) -> List[str]:
        """Returns candidate formatted dates (Turkish and English locale)."""
        formats = []
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            m_idx = dt.month - 1
            # Format 1: Turkish month (e.g. "Ağu 22, 2026 12:00:00 AM")
            formats.append(f"{TURKISH_MONTHS[m_idx]} {dt.day}, {dt.year} 12:00:00 AM")
            # Format 2: English month (e.g. "Aug 22, 2026 12:00:00 AM")
            formats.append(f"{ENGLISH_MONTHS[m_idx]} {dt.day}, {dt.year} 12:00:00 AM")
            # Format 3: DD.MM.YYYY
            formats.append(dt.strftime("%d.%m.%Y"))
        except Exception:
            formats.append("Sep 15, 2026 12:00:00 AM")
        return formats

    def check_route(self, task: TrackingTask) -> CheckResult:
        origin_station = self.get_station_by_name(task.origin)
        dest_station = self.get_station_by_name(task.destination)

        origin_name = origin_station["name"] if origin_station else task.origin
        dest_name = dest_station["name"] if dest_station else task.destination
        origin_id = int(origin_station["id"]) if (origin_station and str(origin_station["id"]).isdigit()) else 60
        dest_id = int(dest_station["id"]) if (dest_station and str(dest_station["id"]).isdigit()) else 14

        date_candidates = self._format_dates(task.date)
        last_error = None

        for endpoint in self.ENDPOINTS:
            for api_date in date_candidates:
                payload = {
                    "kanalKodu": "3",
                    "dil": 0,
                    "seferSorgulamaKriterWSDVO": {
                        "binisIstasyonu": origin_name,
                        "binisIstasyonId": origin_id,
                        "binisIstasyonu_Id": origin_id,
                        "inisIstasyonu": dest_name,
                        "inisIstasyonId": dest_id,
                        "inisIstasyonu_Id": dest_id,
                        "gidisTarih": api_date,
                        "bolgeselGelsin": False,
                        "islemTipi": 0,
                        "yolcuSayisi": max(1, task.min_seats),
                        "aktarmalarGelsin": True
                    }
                }

                try:
                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=self.HEADERS,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=8) as res:
                        raw_response = res.read().decode("utf-8")
                        data = json.loads(raw_response)
                        parsed_result = self._parse_tcdd_response(task, data, origin_name, dest_name)
                        if parsed_result.success:
                            return parsed_result
                except Exception as e:
                    last_error = e
                    continue

        # If live API is unreachable or returned error
        err_msg = str(last_error) if last_error else "TCDD servers returned empty response"
        return CheckResult(
            task_id=task.id,
            success=False,
            found=False,
            seats_count=0,
            message=f"TCDD Live Check ({origin_name} ➔ {dest_name} on {task.date}): {err_msg}",
            error_message=err_msg
        )

    def _parse_tcdd_response(self, task: TrackingTask, data: Dict[str, Any], origin_name: str, dest_name: str) -> CheckResult:
        """Parses TCDD JSON response and extracts all train trips, times, and seat breakdowns."""
        services: List[ServiceInfo] = []
        total_seats = 0

        sefer_list = (
            data.get("seferListesi", []) or 
            data.get("cevapBilgileri", {}).get("seferListesi", []) or
            data.get("seferSorgulamaSonucList", [])
        )

        checked_trains_summary = []

        for sefer in sefer_list:
            train_name = sefer.get("trenAdi") or sefer.get("seferAdi") or f"YHT {sefer.get('trenNo', '')}"
            dep_time = sefer.get("binisSaati") or sefer.get("kalkisSaati", "")
            arr_time = sefer.get("inisSaati") or sefer.get("varisSaati", "")

            # Filter by time if requested
            if task.time_filter and not self._match_time_filter(dep_time, task.time_filter):
                continue

            # Parse wagons and seat availability
            vagon_tipleri = (
                sefer.get("vagonTipleriBosYerUcret", []) or 
                sefer.get("vagonListesi", []) or
                sefer.get("vagonTipiBosYerList", [])
            )
            class_breakdown = {}
            train_seats = 0

            for vagon in vagon_tipleri:
                tip = vagon.get("vagonTipAdi") or vagon.get("vagonTipi", "Pulman")
                bos_yer = int(vagon.get("bosYer", 0) or vagon.get("kalanKoltukSayisi", 0))
                
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
            msg = f"🎉 {detail_msg} from {origin_name} to {dest_name} on {task.date}."
        else:
            if checked_trains_summary:
                msg = f"Checked {len(checked_trains_summary)} trains on {task.date} [{', '.join(checked_trains_summary[:4])}]: All Sold Out (0 seats). Monitoring for cancellations..."
            else:
                msg = f"No scheduled trains found between {origin_name} and {dest_name} on {task.date}."

        return CheckResult(
            task_id=task.id,
            success=True,
            found=found,
            seats_count=total_seats,
            services=services,
            message=msg
        )

    def _match_time_filter(self, dep_time: str, filter_str: str) -> bool:
        if not dep_time or not filter_str:
            return True
        filter_str = filter_str.strip()
        
        # Exact hour match e.g. "16:35"
        if ":" in filter_str and "-" not in filter_str:
            return filter_str in dep_time

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
