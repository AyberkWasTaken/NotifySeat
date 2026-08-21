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
    {"id": "60", "name": "İstanbul(Söğütlüçeşme)", "city": "İstanbul"},
    {"id": "23", "name": "İstanbul(Halkalı)", "city": "İstanbul"},
    {"id": "58", "name": "İstanbul(Pendik)", "city": "İstanbul"},
    {"id": "55", "name": "İstanbul(Bostancı)", "city": "İstanbul"},
    {"id": "20", "name": "İstanbul(Bakırköy)", "city": "İstanbul"},
    {"id": "2", "name": "Ankara Gar", "city": "Ankara"},
    {"id": "592", "name": "Eryaman YHT", "city": "Ankara"},
    {"id": "14", "name": "Eskişehir", "city": "Eskişehir"},
    {"id": "26", "name": "Konya", "city": "Konya"},
    {"id": "40", "name": "Konya(Selçuklu YHT)", "city": "Konya"},
    {"id": "31", "name": "Karaman", "city": "Karaman"},
    {"id": "36", "name": "Sivas", "city": "Sivas"},
    {"id": "52", "name": "Yozgat YHT", "city": "Yozgat"},
    {"id": "4", "name": "İzmir(Basmane)", "city": "İzmir"},
    {"id": "5", "name": "İzmir(Alsancak)", "city": "İzmir"},
    {"id": "1", "name": "Adana", "city": "Adana"},
    {"id": "10", "name": "Bilecik YHT", "city": "Bilecik"},
    {"id": "18", "name": "Kayseri", "city": "Kayseri"},
    {"id": "32", "name": "Kars", "city": "Kars"},
    {"id": "15", "name": "Kırıkkale YHT", "city": "Kırıkkale"},
    {"id": "11", "name": "Bolu", "city": "Bolu"},
    {"id": "61", "name": "İzmit YHT", "city": "Kocaeli"},
    {"id": "19", "name": "Gebze", "city": "Kocaeli"},
    {"id": "7", "name": "Arifiye", "city": "Sakarya"},
    {"id": "27", "name": "Kütahya", "city": "Kütahya"},
    {"id": "3", "name": "Afyon A.Çetinkaya", "city": "Afyonkarahisar"},
    {"id": "13", "name": "Denizli", "city": "Denizli"},
    {"id": "28", "name": "Malatya", "city": "Malatya"},
    {"id": "12", "name": "Diyarbakır", "city": "Diyarbakır"},
    {"id": "16", "name": "Gaziantep", "city": "Gaziantep"}
]


class TCDDProvider(BaseProvider):
    """Integrates with TCDD train ticketing system."""

    API_URL = "https://api-yebsp.tcddtasimacilik.gov.tr/sefer/seferSorgula"
    BOOKING_URL = "https://ebilet.tcddtasimacilik.gov.tr"

    HEADERS = {
        "Authorization": "Basic ZGl0cmF2b3llYnNwOmRpdHJhMzQhdm8u",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://ebilet.tcddtasimacilik.gov.tr",
        "Referer": "https://ebilet.tcddtasimacilik.gov.tr/"
    }

    @property
    def transport_type(self) -> TransportType:
        return TransportType.TCDD

    @property
    def name(self) -> str:
        return "TCDD Train (YHT & Mainline)"

    def search_stations(self, query: str) -> List[Dict[str, str]]:
        q = query.lower().strip()
        matches = []
        for s in TCDD_STATIONS:
            if q in s["name"].lower() or q in s["city"].lower():
                matches.append({"id": s["id"], "name": s["name"], "city": s["city"]})
        return matches

    def get_station_by_name(self, name: str) -> Optional[Dict[str, str]]:
        clean_name = name.lower().replace(" ", "").replace("(", "").replace(")", "").replace("ı", "i")
        for s in TCDD_STATIONS:
            s_clean = s["name"].lower().replace(" ", "").replace("(", "").replace(")", "").replace("ı", "i")
            if clean_name in s_clean or s_clean in clean_name:
                return s
        return None

    def get_popular_routes(self) -> List[Dict[str, str]]:
        return [
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Ankara Gar", "label": "İstanbul (Söğütlüçeşme) ➔ Ankara Gar (YHT)"},
            {"origin": "Ankara Gar", "destination": "İstanbul(Söğütlüçeşme)", "label": "Ankara Gar ➔ İstanbul (Söğütlüçeşme) (YHT)"},
            {"origin": "İstanbul(Halkalı)", "destination": "Ankara Gar", "label": "İstanbul (Halkalı) ➔ Ankara Gar (YHT)"},
            {"origin": "Ankara Gar", "destination": "Eskişehir", "label": "Ankara Gar ➔ Eskişehir (YHT)"},
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Eskişehir", "label": "İstanbul ➔ Eskişehir (YHT)"},
            {"origin": "Ankara Gar", "destination": "Konya", "label": "Ankara Gar ➔ Konya (YHT)"},
            {"origin": "İstanbul(Söğütlüçeşme)", "destination": "Konya", "label": "İstanbul ➔ Konya (YHT)"},
            {"origin": "Ankara Gar", "destination": "Sivas", "label": "Ankara Gar ➔ Sivas (YHT)"},
            {"origin": "Ankara Gar", "destination": "Karaman", "label": "Ankara Gar ➔ Karaman (YHT)"},
            {"origin": "İzmir(Basmane)", "destination": "Eskişehir", "label": "İzmir (Basmane) ➔ Eskişehir (Ege Ekspresi)"}
        ]

    def _format_api_date(self, date_str: str) -> str:
        """Convert YYYY-MM-DD to 'Mon DD, YYYY 00:00:00 AM' format expected by TCDD API."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            # e.g. "Sep 15, 2026 12:00:00 AM"
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            return f"{month_names[dt.month - 1]} {dt.day}, {dt.year} 12:00:00 AM"
        except Exception:
            return "Sep 15, 2026 12:00:00 AM"

    def check_route(self, task: TrackingTask) -> CheckResult:
        origin_station = self.get_station_by_name(task.origin)
        dest_station = self.get_station_by_name(task.destination)

        origin_name = origin_station["name"] if origin_station else task.origin
        dest_name = dest_station["name"] if dest_station else task.destination
        origin_id = origin_station["id"] if origin_station else (task.origin_id or "60")
        dest_id = dest_station["id"] if dest_station else (task.destination_id or "2")

        api_date = self._format_api_date(task.date)

        payload = {
            "kanalKodu": 3,
            "dil": 0,
            "seferSorgulamaKriterWSDTO": {
                "binisIstasyonu": origin_name,
                "binisIstasyonu_Id": int(origin_id) if str(origin_id).isdigit() else 60,
                "inisIstasyonu": dest_name,
                "inisIstasyonu_Id": int(dest_id) if str(dest_id).isdigit() else 2,
                "gidisTarih": api_date,
                "bolgeselGelsin": False,
                "islemTipi": 0,
                "yolcuSayisi": max(1, task.min_seats),
                "aktarmalarGelsin": True
            }
        }

        try:
            req = urllib.request.Request(
                self.API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=self.HEADERS,
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as res:
                raw_response = res.read().decode("utf-8")
                data = json.loads(raw_response)
                return self._parse_tcdd_response(task, data)
        except Exception as e:
            logger.warning(f"TCDD API call returned: {e}. Checking fallback parsing.")
            return CheckResult(
                task_id=task.id,
                success=False,
                found=False,
                seats_count=0,
                message=f"Network error or TCDD API unreachable: {str(e)}",
                error_message=str(e)
            )

    def _parse_tcdd_response(self, task: TrackingTask, data: Dict[str, Any]) -> CheckResult:
        """Parses TCDD JSON response and filters by user constraints."""
        services: List[ServiceInfo] = []
        total_seats = 0

        sefer_list = data.get("seferListesi", []) or data.get("cevapBilgileri", {}).get("seferListesi", [])
        if not sefer_list and isinstance(data.get("seferSorgulamaSonucList"), list):
            sefer_list = data.get("seferSorgulamaSonucList", [])

        for sefer in sefer_list:
            train_name = sefer.get("trenAdi") or sefer.get("seferAdi") or f"YHT {sefer.get('trenNo', '')}"
            dep_time = sefer.get("binisSaati") or sefer.get("kalkisSaati", "")
            arr_time = sefer.get("inisSaati") or sefer.get("varisSaati", "")

            # Filter by time if requested
            if task.time_filter:
                if not self._match_time_filter(dep_time, task.time_filter):
                    continue

            # Parse wagons and seat availability
            vagon_tipleri = sefer.get("vagonTipleriBosYerUcret", []) or sefer.get("vagonListesi", [])
            class_breakdown = {}
            service_seats = 0

            for vagon in vagon_tipleri:
                tip = vagon.get("vagonTipAdi") or vagon.get("vagonTipi", "Pulman")
                bos_yer = int(vagon.get("bosYer", 0) or vagon.get("kalanKoltukSayisi", 0))
                
                # Check class filter
                if task.seat_class and task.seat_class != "ANY":
                    if task.seat_class.lower() not in tip.lower():
                        continue

                class_breakdown[tip] = bos_yer
                service_seats += bos_yer

            if service_seats > 0:
                services.append(ServiceInfo(
                    service_id=str(sefer.get("seferId") or sefer.get("trenNo", "")),
                    service_name=train_name,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    origin=task.origin,
                    destination=task.destination,
                    date=task.date,
                    total_available_seats=service_seats,
                    class_breakdown=class_breakdown,
                    booking_url=self.BOOKING_URL,
                    operator="TCDD Taşımacılık",
                    notes="Direct seat availability found on TCDD YHT"
                ))
                total_seats += service_seats

        found = total_seats >= task.min_seats
        msg = f"Found {total_seats} available seat(s) across {len(services)} train(s)!" if found else "No available seats matching criteria."

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
        
        # Exact hour match e.g. "08:30"
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
