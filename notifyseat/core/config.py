"""Configuration management for NotifySeat."""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import json
import os
from pathlib import Path


DEFAULT_CONFIG_PATH = Path.home() / ".notifyseat" / "config.json"


@dataclass
class EmailConfig:
    enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True
    username: str = ""
    password: str = ""
    sender_email: str = ""
    recipient_email: str = ""


@dataclass
class TelegramConfig:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class DiscordConfig:
    enabled: bool = False
    webhook_url: str = ""


@dataclass
class WhatsAppConfig:
    enabled: bool = False
    phone_number: str = ""
    apikey: str = ""


@dataclass
class DesktopConfig:
    enabled: bool = True
    sound_enabled: bool = True
    sound_type: str = "chime"  # chime, bell, custom


@dataclass
class SMSConfig:
    enabled: bool = False
    provider: str = "netgsm"  # netgsm, twilio, custom_webhook
    api_key: str = ""
    api_secret: str = ""
    phone_number: str = ""
    sender_header: str = ""


@dataclass
class WebhookConfig:
    enabled: bool = False
    url: str = ""
    method: str = "POST"
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class AppConfig:
    email: EmailConfig = field(default_factory=EmailConfig)
    whatsapp: WhatsAppConfig = field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    desktop: DesktopConfig = field(default_factory=DesktopConfig)
    sms: SMSConfig = field(default_factory=SMSConfig)
    webhook: WebhookConfig = field(default_factory=WebhookConfig)
    default_check_interval: int = 300
    user_name: str = "Ayberk"
    web_host: str = "127.0.0.1"
    web_port: int = 8080
    tcdd_token: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "email": asdict(self.email),
            "whatsapp": asdict(self.whatsapp),
            "telegram": asdict(self.telegram),
            "discord": asdict(self.discord),
            "desktop": asdict(self.desktop),
            "sms": asdict(self.sms),
            "webhook": asdict(self.webhook),
            "default_check_interval": self.default_check_interval,
            "user_name": self.user_name,
            "web_host": self.web_host,
            "web_port": self.web_port,
            "tcdd_token": self.tcdd_token
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        cfg = cls()
        if "email" in data:
            cfg.email = EmailConfig(**data["email"])
        if "whatsapp" in data:
            cfg.whatsapp = WhatsAppConfig(**data["whatsapp"])
        if "telegram" in data:
            cfg.telegram = TelegramConfig(**data["telegram"])
        if "discord" in data:
            cfg.discord = DiscordConfig(**data["discord"])
        if "desktop" in data:
            cfg.desktop = DesktopConfig(**data["desktop"])
        if "sms" in data:
            cfg.sms = SMSConfig(**data["sms"])
        if "webhook" in data:
            cfg.webhook = WebhookConfig(**data["webhook"])
        if "default_check_interval" in data:
            cfg.default_check_interval = int(data["default_check_interval"])
        if "user_name" in data:
            cfg.user_name = str(data["user_name"])
        if "web_host" in data:
            cfg.web_host = str(data["web_host"])
        if "web_port" in data:
            cfg.web_port = int(data["web_port"])
        if "tcdd_token" in data:
            cfg.tcdd_token = str(data["tcdd_token"])
        return cfg


class ConfigManager:
    """Manages reading and writing application configuration to local disk."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = self.load()

    def load(self) -> AppConfig:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return AppConfig.from_dict(data)
            except Exception:
                return AppConfig()
        cfg = AppConfig()
        self.save(cfg)
        return cfg

    def save(self, config: Optional[AppConfig] = None) -> None:
        if config is not None:
            self.config = config
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, indent=2, ensure_ascii=False)

    def get(self) -> AppConfig:
        return self.config
