"""Run inside the backend container: python -m agent_app.auth.diagnose.

Does not send mail unless --send-to is explicitly supplied. Never prints
credentials, SMTP conversation contents, verification codes or account data.
"""
import argparse
import os
import socket
from pathlib import Path
from dotenv import dotenv_values

from .mailer import MailDeliveryError, delivery_error, make_message, smtp_config, smtp_connection


def main() -> int:
    parser = argparse.ArgumentParser(description='检查当前后端环境中的 SMTP 配置、DNS、TLS 和授权认证')
    parser.add_argument('--send-to', help='额外向指定邮箱发送一封诊断邮件；该邮件不包含有效验证码')
    args = parser.parse_args()
    print('SMTP diagnostic (authorization code is never displayed)', flush=True)
    env_path = Path(__file__).resolve().parent.parent / '.env'
    print('Environment file exists:', env_path.exists(), flush=True)
    if env_path.exists():
        saved = dotenv_values(env_path)
        different = [key for key in ('SMTP_HOST', 'SMTP_PORT', 'SMTP_SECURITY', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM_EMAIL')
                     if key in saved and saved[key] is not None and os.getenv(key) != saved[key]]
        if different:
            print('WARNING: process environment differs from .env for: ' + ', '.join(different), flush=True)
            print('Recreate the Compose backend container to load the updated env_file.', flush=True)
    try:
        config = smtp_config()
        print(f"Configuration: host={config['host']} port={config['port']} security={config['security']}", flush=True)
        print('Credentials: present; sender matches login:', config['sender'].lower() == config['username'].lower(), flush=True)
        socket.getaddrinfo(config['host'], config['port'], type=socket.SOCK_STREAM)
        print('DNS: OK', flush=True)
        with smtp_connection(config, on_stage=lambda stage: print('Stage:', stage, flush=True)) as client:
            print('TLS connection and SMTP authentication: OK', flush=True)
            if args.send_to:
                from .service import normalize_email
                recipient = normalize_email(args.send_to)
                message = make_message(config, recipient, '【工业时序智能体】邮件投递诊断', '这是一封邮件投递诊断测试邮件，不包含有效验证码，无需回复。')
                client.send_message(message, from_addr=config['sender'], to_addrs=[recipient])
                print('Test email: accepted by SMTP. Check inbox and spam; acceptance does not confirm inbox delivery.', flush=True)
            else:
                print('No email sent. To test delivery explicitly, add: --send-to your-address@example.com', flush=True)
        return 0
    except MailDeliveryError as exc:
        print(f'FAILED: category={exc.category} stage={exc.stage} exception_type={exc.exception_type} errno={exc.error_number} smtp_status={exc.smtp_status}; {exc}', flush=True)
    except (OSError, socket.gaierror) as exc:
        error = delivery_error(exc)
        print(f'FAILED: category={error.category}; {error}', flush=True)
    except Exception as exc:
        # Do not print raw exception messages: they may contain supplied inputs.
        print(f'FAILED: exception_type={type(exc).__name__}', flush=True)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
