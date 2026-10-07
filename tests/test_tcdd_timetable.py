"""Unit tests for TCDD timetable and live seat availability fetching."""
import unittest
from unittest.mock import patch, MagicMock
from notifyseat.providers.tcdd import TCDDProvider, tcdd_utc_to_local
from notifyseat.core.models import TrackingTask, TransportType


class TestTCDDTimetable(unittest.TestCase):
    def setUp(self):
        self.provider = TCDDProvider()

    def test_tcdd_utc_to_local(self):
        # 06:20 UTC should be 09:20 local (UTC+3)
        d_str, t_str = tcdd_utc_to_local("2026-10-10T06:20:00")
        self.assertEqual(d_str, "2026-10-10")
        self.assertEqual(t_str, "09:20")

        # Handles date without T
        d_str2, t_str2 = tcdd_utc_to_local("2026-10-10 15:30:00")
        self.assertEqual(d_str2, "2026-10-10")
        self.assertEqual(t_str2, "18:30")

        # Handles empty
        self.assertEqual(tcdd_utc_to_local(""), ("", ""))
        self.assertEqual(tcdd_utc_to_local(None), ("", ""))

    @patch("requests.post")
    def test_get_trains_by_station_and_date(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {
                "trainNumber": "81001",
                "trainName": "81001 ANKARA - İSTANBUL",
                "tsDepartureTime": "2026-10-10T03:00:00",
                "lineStartStationId": 98,
                "lineEndStationId": 1325
            }
        ]
        mock_post.return_value = mock_resp

        trains = self.provider.get_trains_by_station_and_date(98, "10-10-2026")
        self.assertEqual(len(trains), 1)
        self.assertEqual(trains[0]["trainNumber"], "81001")

    @patch("requests.post")
    def test_get_seat_availability_for_train(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "seatMaps": [
                {
                    "cabinClass": {"name": "EKONOMİ"},
                    "seatMapTemplate": {"name": "2+1 PULMAN", "car": {"name": "1. Araba"}},
                    "allocationSeats": [{"seatNumber": "1A"}],
                    "seatPrices": [
                        {"seatNumber": "1A", "price": 350.0, "cabinClassId": 1},
                        {"seatNumber": "1B", "price": 350.0, "cabinClassId": 1},
                        {"seatNumber": "2A", "price": 350.0, "cabinClassId": 1},
                        # Handicapped seat should be filtered out
                        {"seatNumber": "9H", "price": 350.0, "cabinClassId": 12}
                    ]
                }
            ]
        }
        mock_post.return_value = mock_resp

        tot, cls_bd, car_bd, min_p, curr = self.provider.get_seat_availability_for_train(191610, 98, 93)
        # 1A is allocated, 9H is handicapped. So 1B and 2A remain = 2 seats.
        self.assertEqual(tot, 2)
        self.assertEqual(cls_bd.get("Ekonomi"), 2)
        self.assertEqual(min_p, 350.0)
        self.assertEqual(curr, "TRY")

    @patch.object(TCDDProvider, "get_seat_availability_for_train")
    @patch.object(TCDDProvider, "get_trains_by_station_and_date")
    def test_get_scheduled_trains_matching(self, mock_load_trains, mock_seats):
        # Origin: Ankara Gar (id: 98), Dest: Eskişehir (id: 93)
        mock_load_trains.side_effect = [
            # Trains at origin (98)
            [
                {
                    "trainNumber": "81002",
                    "trainName": "81002 ANKARA - ESKİŞEHİR",
                    "trainId": 1001,
                    "lineStartStationId": 98,
                    "lineEndStationId": 93,
                    "tsDepartureTime": "2026-10-10T05:00:00"
                }
            ],
            # Trains at dest (93)
            [
                {
                    "trainNumber": "81002",
                    "tsArrivalTime": "2026-10-10T06:25:00"
                }
            ]
        ]
        # Seats mock: 5 economy seats
        mock_seats.return_value = (5, {"Ekonomi": 5}, [{"class": "Ekonomi", "car": "1", "count": 5}], 280.0, "TRY")

        trains = self.provider.get_scheduled_trains("Ankara Gar", "Eskişehir", "10-10-2026")
        self.assertEqual(len(trains), 1)
        t = trains[0]
        self.assertEqual(t.service_id, "81002")
        # 05:00 UTC -> 08:00 local time
        self.assertEqual(t.departure_time, "08:00")
        # 06:25 UTC -> 09:25 local time
        self.assertEqual(t.arrival_time, "09:25")
        self.assertEqual(t.total_available_seats, 5)
        self.assertEqual(t.class_breakdown, {"Ekonomi": 5})

    @patch.object(TCDDProvider, "get_scheduled_trains")
    @patch.object(TCDDProvider, "_check_via_ytp_api", return_value=None)
    def test_check_route_fallback(self, mock_ytp, mock_get_scheduled):
        from notifyseat.core.models import ServiceInfo
        mock_get_scheduled.return_value = [
            ServiceInfo(
                service_id="81002",
                service_name="81002 YHT",
                departure_time="08:00",
                arrival_time="09:25",
                origin="Ankara Gar",
                destination="Eskişehir",
                date="10-10-2026",
                total_available_seats=3,
                class_breakdown={"Ekonomi": 3}
            )
        ]

        task = TrackingTask(
            origin="Ankara Gar",
            destination="Eskişehir",
            date="10-10-2026",
            transport_type=TransportType.TCDD
        )
        res = self.provider.check_route(task)
        self.assertTrue(res.success)
        self.assertTrue(res.found)
        self.assertEqual(res.seats_count, 3)
        self.assertEqual(len(res.services), 1)


if __name__ == "__main__":
    unittest.main()
