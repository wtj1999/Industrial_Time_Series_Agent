# 邮箱验证与账户登录

账户流程：邮箱验证码注册 → 自动登录；用户名或邮箱 + 密码登录；邮箱验证码重置密码 → 返回登录；退出时撤销当前会话。旧账户可用原用户名及密码登录，再从工作台顶部的「绑定安全邮箱」入口验证邮箱并确认当前密码。

## 配置邮件

把 [auth.env.example](../auth.env.example) 中的 `SMTP_*` 配置追加到 `agent_app/.env`，填写自己的发信邮箱和 SMTP 授权码，然后重启后端。不要覆盖原有模型等配置，也不要把授权码提交到 Git 或填入前端环境变量。

- `SMTP_HOST`：邮箱服务商的 SMTP 服务器。
- `SMTP_PORT=465`、`SMTP_SECURITY=ssl`；或端口 587、`SMTP_SECURITY=starttls`。
- `SMTP_USERNAME`、`SMTP_PASSWORD`：发信账户及 SMTP 授权码（通常不同于邮箱登录密码）。
- `SMTP_FROM_EMAIL`：发件地址，通常与登录 SMTP 的账户相同。
- `SMTP_FROM_NAME`：发件人显示名称。

本机从项目根目录启动时，邮件模块也会读取 `agent_app/.env`；Docker Compose 已通过 `env_file` 注入该文件。无 SMTP 配置时，获取验证码返回明确的 503 提示，原有账户仍可正常登录。邮件异步发送；SMTP 连接或认证失败会记录不含验证码、密码的警告，并作废该验证码。界面中的「请求已提交」表示已受理发送请求，不承诺已送达。真实收信需用自己的邮箱配置做一次验收，检查垃圾邮件箱及发件域的投递设置。

## 服务器收不到验证码时的诊断

Outlook.com 的服务地址为 `smtp-mail.outlook.com:587`，使用 STARTTLS，并要求 OAuth2/Modern Auth。[微软官方配置说明](https://support.microsoft.com/en-gb/outlook/pop-imap-and-smtp-settings-for-outlook-com)。当前邮件模块使用 `SMTP.login()` 密码认证，尚未实现 OAuth2；仅替换 Outlook 邮箱及密码不能完成接入。要使用 Outlook.com，需要注册支持个人 Microsoft 账户的应用，配置客户端 ID，并由邮箱所有者完成授权，再实现 OAuth2 令牌管理与 SMTP XOAUTH2 认证。

先同步 `auth/mailer.py`、`auth/service.py` 和 `auth/diagnose.py` 到服务器，再在项目目录执行（此命令只做连接及认证检查，不发送邮件）：

```bash
sudo docker compose exec -T backend python -m agent_app.auth.diagnose
sudo docker compose logs --since=10m --tail=100 backend
```

如需实际投递测试邮件，显式指定收件地址：

```bash
sudo docker compose exec -T backend python -m agent_app.auth.diagnose --send-to your-address@example.com
```

诊断邮件不含有效验证码，不创建账户。SMTP 接受邮件不等于已进入收件箱，还需查看垃圾箱及服务商拦截情况。日志中的 `category=authentication` 表示授权认证失败；`dns`、`timeout`、`tls` 表示解析、连接或加密失败；`sender_refused`、`recipient_refused`、`message_refused` 表示服务商拒绝发件人、收件人或邮件内容；`skipped (email not eligible)` 表示本次用途不符合账户状态，例如对已注册邮箱再次申请注册验证码。不要开启 SMTP 原始协议调试或公开授权码。

## 数据与兼容

- 默认数据库为 `agent_app/auth/auth.sqlite3`，也可用 `AUTH_DB_PATH` 指向持久目录。
- 首次访问账户服务时，在一个事务中导入 `auth/users.json`。保留 `user_id`、用户名和旧密码哈希，数据及模型目录无需迁移。导入标记保证重启后不会重新导入旧密码。
- 旧账户未绑定邮箱时无法通过邮箱重置密码，必须先凭原密码登录并绑定；如果原密码已遗忘，需由管理员核验身份后恢复，不能凭任意邮箱接管。
- 旧密码可继续登录；原有的首次登录哈希升级机制保持原样。新注册密码要求 8–128 个字符，同时包含大写字母、小写字母、数字和英文特殊字符（如 `!@#`）；空格或中文不能代替特殊字符。前端展示并预校验，注册服务再次强制校验；强度不足时不创建账户、不消耗邮箱验证码，可修改密码后继续提交。该策略仅用于注册，不批量修改既有密码，也不强制已有账户改密；登录、绑定邮箱及重置密码沿用现有流程（重置密码仍要求 8–128 个字符且包含字母和数字）。
- 请备份并持久化 SQLite 数据库；仅有旧 `users.json` 无法恢复后来新增的账户、绑定邮箱或密码修改。Compose 默认源码目录挂载会保留此数据库；独立容器部署必须另挂持久卷。
- SQLite 支持同一主机上的多个 worker，不能把各自独立的 SQLite 副本当成多个实例共享账户状态。

## 会话与验证码

- 验证码为随机 6 位数字，10 分钟有效，60 秒内不能重发，每个邮箱每小时最多申请 5 次、每个来源 IP 每小时最多 20 次。
- 每条验证码最多尝试 5 次，按注册、密码重置、邮箱绑定隔离。重发后旧验证码失效，成功使用后删除；验证码和会话令牌只存哈希。
- 注册、密码重置的校验请求受 IP 限制；登录还按来源 IP 和账户限制请求频率。超限返回 429 和 `Retry-After`。
- 对不存在的找回邮箱及已注册的注册邮箱，申请验证码返回相同的受理提示，避免从响应直接判断账户存在性；不向这些地址发送验证码。
- 登录颁发随机 Bearer token，固定有效期 7 天。前端在业务请求中携带 `Authorization`，服务端从会话推导用户身份，忽略调用方伪造的 `X-User-Id`。
- 退出撤销当前 token；密码重置撤销该用户的全部会话；前端遇到 401 清理状态并返回登录。旧浏览器只保存用户 ID 的登录状态需要重新登录。
- 独立 BI 后端也验证 token，本机默认调用 `http://127.0.0.1:8000/api/auth/me`，可通过 `AUTH_SERVICE_URL` 设置账户服务地址，Compose 已配置为 `http://backend:8000`。
- 部署时应启用 HTTPS。反向代理部署若需按真实客户端 IP 限流，应只信任受控代理的转发头，并正确配置 Uvicorn 的可信代理地址，不能信任任意客户端传来的转发头。

验证码过期、单次使用、限流和密码重置撤销旧会话等设计参考 [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)。

## API

| 方法 | 路径 | 请求 |
| --- | --- | --- |
| POST | `/api/auth/send-code` | `email`, `purpose`: `register` / `reset_password` / `bind_email`（绑定需要 token） |
| POST | `/api/auth/register` | `username`, `email`, `code`, `password` |
| POST | `/api/auth/login` | `username`（用户名或邮箱）, `password` |
| POST | `/api/auth/reset-password` | `email`, `code`, `password`（新密码） |
| GET | `/api/auth/me` | Bearer token |
| POST | `/api/auth/logout` | Bearer token |
| POST | `/api/auth/bind-email` | `email`, `code`, `password`（当前密码），Bearer token |

## 验证

```bash
python -m pytest agent_app/auth/test_auth.py agent_app/test_session_ownership.py bi_app/test_auth.py bi_app/test_api.py bi_app/ng/test_ng.py -q
cd frontend
npm run build
```

认证测试使用独立临时数据库、模拟 SMTP，不会读写正式账户或发送真实邮件。
