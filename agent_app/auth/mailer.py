"""SMTP delivery with mandatory TLS and no credential/code logging."""
import os
import smtplib
import socket
import ssl
from contextlib import contextmanager
from pathlib import Path
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')


class MailDeliveryError(Exception):
    def __init__(self, message: str, category: str = 'delivery', smtp_status: int | None = None):
        super().__init__(message)
        self.category = category
        self.smtp_status = smtp_status
        self.exception_type: str | None = None
        self.error_number: int | None = None
        self.stage: str | None = None


def delivery_error(exc: Exception) -> MailDeliveryError:
    """Classify failures without exposing raw SMTP responses or credentials."""
    status = getattr(exc, 'smtp_code', None)
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        category, message = 'authentication', 'SMTP 认证失败，请检查邮箱授权码及 SMTP 服务状态'
    elif isinstance(exc, socket.gaierror):
        category, message = 'dns', '无法解析 SMTP 域名，请检查服务器 DNS'
    elif isinstance(exc, (TimeoutError, socket.timeout)):
        category, message = 'timeout', '连接 SMTP 服务超时，请检查服务器出站网络及端口限制'
    elif isinstance(exc, ssl.SSLError):
        category, message = 'tls', 'SMTP TLS 连接失败，请检查证书、系统时间及端口配置'
    elif isinstance(exc, ConnectionRefusedError):
        category, message = 'connection_refused', 'SMTP 连接被拒绝，请检查出站端口及目标服务'
    elif isinstance(exc, ConnectionResetError):
        category, message = 'connection_reset', 'SMTP 连接被重置，请检查网络设备或服务端连接策略'
    elif isinstance(exc, smtplib.SMTPServerDisconnected):
        category, message = 'disconnected', 'SMTP 连接被提前关闭，请结合失败阶段检查网络及服务端策略'
    elif isinstance(exc, smtplib.SMTPSenderRefused):
        category, message = 'sender_refused', 'SMTP 拒绝发件地址，请检查发件地址与发信账户是否一致'
    elif isinstance(exc, smtplib.SMTPRecipientsRefused):
        category, message = 'recipient_refused', 'SMTP 拒绝收件地址，请检查收件邮箱'
    elif isinstance(exc, smtplib.SMTPDataError):
        category, message = 'message_refused', 'SMTP 拒收邮件内容，请检查发信额度或邮箱服务商限制'
    elif isinstance(exc, smtplib.SMTPNotSupportedError):
        category, message = 'unsupported', 'SMTP 服务不支持当前加密或认证方式'
    else:
        category, message = 'connection', 'SMTP 连接或发送失败，请检查服务器网络及邮件服务状态'
    error = MailDeliveryError(message, category, status)
    error.exception_type = type(exc).__name__
    error.error_number = getattr(exc, 'errno', None)
    return error


def smtp_config() -> dict:
    host = os.getenv('SMTP_HOST', '').strip()
    sender = os.getenv('SMTP_FROM_EMAIL', '').strip()
    username = os.getenv('SMTP_USERNAME', '').strip()
    password = os.getenv('SMTP_PASSWORD', '')
    security = os.getenv('SMTP_SECURITY', 'ssl').lower()
    if not host or not sender or not username or not password or security not in ('ssl', 'starttls'):
        raise MailDeliveryError('邮件服务未配置，请联系管理员配置 SMTP', 'configuration')
    try:
        port = int(os.getenv('SMTP_PORT', '465' if security == 'ssl' else '587'))
        if not 1 <= port <= 65535:
            raise ValueError('Invalid SMTP port')
    except ValueError as exc:
        raise MailDeliveryError('邮件服务配置不正确，请联系管理员', 'configuration') from exc
    return dict(host=host, sender=sender, username=username, password=password, security=security, port=port)


def make_message(config: dict, email: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = formataddr((os.getenv('SMTP_FROM_NAME', '工业时序智能体'), config['sender']))
    message['To'] = email
    message['Date'] = formatdate(localtime=False)
    message['Message-ID'] = make_msgid(domain=config['sender'].rsplit('@', 1)[-1])
    message.set_content(body)
    return message


@contextmanager
def smtp_connection(config: dict, on_stage=None):
    client = None
    stage = 'connect_tls_greeting' if config['security'] == 'ssl' else 'connect_greeting'
    def report(value):
        nonlocal stage
        stage = value
        if on_stage:
            on_stage(value)
    try:
        context = ssl.create_default_context()
        report(stage)
        if config['security'] == 'ssl':
            client = smtplib.SMTP_SSL(config['host'], config['port'], timeout=10, context=context)
        else:
            client = smtplib.SMTP(config['host'], config['port'], timeout=10)
        if config['security'] == 'starttls':
            report('starttls')
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        report('authentication')
        client.login(config['username'], config['password'])
        report('session_ready')
        yield client
    except (OSError, smtplib.SMTPException) as exc:
        error = delivery_error(exc)
        error.stage = stage
        raise error from exc
    finally:
        if client is not None:
            # An error in QUIT must not turn an already accepted message into a
            # failed verification challenge. Always close the socket as well.
            try:
                client.quit()
            except (OSError, smtplib.SMTPException):
                pass
            finally:
                client.close()


def send_code(email: str, code: str, purpose: str):
    config = smtp_config()
    action = {'register': '注册账户', 'reset_password': '重置密码', 'bind_email': '绑定邮箱'}[purpose]
    message = make_message(config, email, f'【工业时序智能体】{action}验证码', f'您正在{action}。\n\n验证码：{code}\n\n10 分钟内有效，仅可使用一次。请勿向任何人透露验证码。\n如果不是您本人操作，请忽略此邮件。')
    with smtp_connection(config) as client:
        client.send_message(message, from_addr=config['sender'], to_addrs=[email])
