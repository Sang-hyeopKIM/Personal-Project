"""항공권 특가 알리미 - 알림 모듈

이메일(SMTP) 및 텔레그램 봇을 통한 알림을 지원합니다.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from models import FlightOffer

logger = logging.getLogger(__name__)


class EmailNotifier:
    """이메일(SMTP) 알림"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        sender: str,
        recipients: list[str],
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender = sender
        self.recipients = recipients
        self.use_tls = use_tls

    def send(self, subject: str, body_html: str):
        """이메일을 발송합니다."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = ", ".join(self.recipients)
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.sender, self.recipients, msg.as_string())
            logger.info("이메일 발송 완료: %s", subject)
        except Exception as e:
            logger.error("이메일 발송 실패: %s", e)

    def send_flight_alert(
        self, offers: list[FlightOffer], is_new_low: bool = False
    ):
        """항공권 특가 알림 이메일을 발송합니다."""
        if not offers:
            return

        tag = "🔥 역대 최저가!" if is_new_low else "✈️ 특가 알림"
        best = offers[0]
        subject = (
            f"{tag} {best.destination_name} "
            f"{best.total_price:,.0f}{best.currency} "
            f"({best.departure_date}~{best.return_date})"
        )

        rows = ""
        for i, offer in enumerate(offers, 1):
            direct = "직항" if offer.is_direct else "경유"
            carrier = (
                offer.outbound_segments[0].carrier_name
                if offer.outbound_segments else "-"
            )
            rows += f"""
            <tr>
                <td>{i}</td>
                <td>{offer.destination_name}</td>
                <td>{offer.departure_date} ~ {offer.return_date} ({offer.stay_days}박)</td>
                <td>{carrier} ({direct})</td>
                <td style="text-align:right;font-weight:bold;">
                    {offer.total_price:,.0f} {offer.currency}
                </td>
                <td style="text-align:right;">
                    {offer.price_per_person:,.0f} {offer.currency}
                </td>
            </tr>"""

        body = f"""
        <html>
        <body style="font-family: 'Malgun Gothic', sans-serif;">
            <h2>{tag} 항공권 특가 정보</h2>
            <p>4인 가족 (성인 2 + 아동 2) 왕복 기준</p>
            <table border="1" cellpadding="8" cellspacing="0"
                   style="border-collapse:collapse; width:100%;">
                <thead style="background-color:#f0f0f0;">
                    <tr>
                        <th>#</th>
                        <th>목적지</th>
                        <th>일정</th>
                        <th>항공사</th>
                        <th>총액 (4인)</th>
                        <th>1인당</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="color:#888; font-size:12px; margin-top:16px;">
                * 가격은 조회 시점 기준이며 변동될 수 있습니다.<br>
                * 항공권 특가 알리미에서 자동 발송된 메일입니다.
            </p>
        </body>
        </html>
        """
        self.send(subject, body)


class TelegramNotifier:
    """텔레그램 봇 알림"""

    API_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.url = self.API_URL.format(token=bot_token)

    def send(self, message: str, parse_mode: str = "HTML"):
        """텔레그램 메시지를 발송합니다."""
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
        }
        try:
            resp = requests.post(self.url, json=payload, timeout=10)
            resp.raise_for_status()
            logger.info("텔레그램 메시지 발송 완료")
        except requests.RequestException as e:
            logger.error("텔레그램 발송 실패: %s", e)

    def send_flight_alert(
        self, offers: list[FlightOffer], is_new_low: bool = False
    ):
        """항공권 특가 알림을 텔레그램으로 발송합니다."""
        if not offers:
            return

        tag = "🔥 역대 최저가!" if is_new_low else "✈️ 특가 발견"
        best = offers[0]

        lines = [
            f"<b>{tag}</b>",
            f"<b>{best.destination_name}</b> 왕복 항공권",
            f"👨‍👩‍👧‍👦 4인 가족 (성인2 + 아동2)",
            "",
        ]

        for i, offer in enumerate(offers[:5], 1):
            direct = "직항" if offer.is_direct else "경유"
            carrier = (
                offer.outbound_segments[0].carrier_name
                if offer.outbound_segments else "-"
            )
            lines.extend([
                f"<b>#{i}</b> {offer.departure_date} ~ {offer.return_date} ({offer.stay_days}박)",
                f"   {carrier} | {direct}",
                f"   💰 총 <b>{offer.total_price:,.0f}</b> {offer.currency}"
                f" (1인 {offer.price_per_person:,.0f})",
                "",
            ])

        lines.append(
            "<i>* 가격은 조회 시점 기준이며 변동될 수 있습니다.</i>"
        )
        self.send("\n".join(lines))


class ConsoleNotifier:
    """콘솔 출력 알림 (테스트/디버깅용)"""

    def send_flight_alert(
        self, offers: list[FlightOffer], is_new_low: bool = False
    ):
        if not offers:
            return

        tag = "*** 역대 최저가! ***" if is_new_low else "--- 특가 발견 ---"
        print(f"\n{'='*60}")
        print(f"  {tag}")
        print(f"  4인 가족 (성인2 + 아동2) 왕복 기준")
        print(f"{'='*60}")

        for i, offer in enumerate(offers[:10], 1):
            print(f"\n  #{i} {offer.summary()}")
            if offer.outbound_segments:
                seg = offer.outbound_segments[0]
                print(f"     가는편: {seg.flight_number} "
                      f"{seg.departure_time} → {seg.arrival_time}")
            if offer.return_segments:
                seg = offer.return_segments[0]
                print(f"     오는편: {seg.flight_number} "
                      f"{seg.departure_time} → {seg.arrival_time}")

        print(f"\n{'='*60}\n")
