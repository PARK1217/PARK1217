# 배포 — Proxmox LXC + Docker + Cloudflare Tunnel + Cloudflare Access

앱이 로컬에서 다 돌아간 뒤에 이 순서대로 한다. 도메인은 `fridge.chobihome.com`으로 적어 두었고, 바꾸려면 `.env`의 `APP_DOMAIN`과 Cloudflare 쪽 호스트명만 바꾸면 된다.

## 0. 준비물

- Proxmox에 LXC 하나 (Debian 12 템플릿, 비특권, **features: nesting=1,keyctl=1** — Docker가 LXC 안에서 돌려면 필요)
  - 2 vCPU · 1 GB RAM · 8 GB 디스크면 충분하다.
- Cloudflare 계정에 `chobihome.com`이 올라가 있고 Zero Trust(무료 플랜)가 켜져 있을 것.

## 1. LXC 안에 Docker

```bash
apt update && apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
docker compose version        # v2.24 이상이면 된다
```

## 2. 앱 올리기

```bash
git clone <저장소> /opt/fridge-dict && cd /opt/fridge-dict
cp .env.example .env          # HOST_PORT, APP_DOMAIN, TZ 확인
docker compose up -d --build
curl -s localhost:8080/api/health     # {"ok":true}
docker compose logs --tail 20         # [seed] recipe: 파일 24건, 새로 24건 … 이 보이면 시드 완료
```

- SQLite는 `/opt/fridge-dict/db/fridge.db`에 생긴다(볼륨). 이 폴더가 백업 대상이다.
- 레시피를 `data/*.json`에 추가한 뒤 `docker compose up -d --build`하면 **없는 id만** 새로 들어간다. 이미 있는 항목은 파일을 바꿔도 DB를 덮어쓰지 않는다(수정은 API로).
- 업데이트: `git pull && docker compose up -d --build`. DB는 볼륨이라 그대로다.

## 3. 백업

```bash
./deploy/backup.sh            # db/backup/fridge-YYYYmmdd-HHMM.db 로 온라인 백업(앱 중단 없음)
```

cron 예시(매일 04:10, 30일 보관):

```
10 4 * * * cd /opt/fridge-dict && ./deploy/backup.sh >/dev/null 2>&1 && find db/backup -name 'fridge-*.db' -mtime +30 -delete
```

Proxmox 쪽에서 LXC 전체 스냅샷·백업(vzdump)을 돌리면 그걸로도 충분하다.

## 4. Cloudflare Tunnel — 두 가지 중 하나

### A. cloudflared를 같은 compose에 사이드카로 (권장, 처음 세팅이면 이쪽)

1. Zero Trust 대시보드 → **Networks → Tunnels → Create a tunnel → Cloudflared** → 이름 `fridge-dict`.
2. 나오는 토큰을 `.env`에 `TUNNEL_TOKEN=...` 으로 추가.
3. 같은 화면의 **Public Hostname**에 추가:
   - Subdomain `fridge`, Domain `chobihome.com`
   - Service: **HTTP**, URL `fridge-dict:8080` (compose 네트워크 안의 서비스 이름)
4. 사이드카 포함으로 다시 올리기:

```bash
docker compose -f docker-compose.yml -f deploy/docker-compose.tunnel.yml up -d
```

이 오버라이드는 앱 포트를 `127.0.0.1`에만 묶는다. LAN의 다른 기기가 8080으로 직접 들어와 `Cf-Access-Authenticated-User-Email` 헤더를 흉내 내는 길을 막기 위해서다. **앱은 이 헤더를 그대로 믿으므로, 터널 말고 다른 길로 앱에 닿을 수 없어야 한다.**

### B. 이미 돌고 있는 cloudflared(고양이 앱 등)에 호스트명만 추가

- 원격 관리 터널이면 대시보드 Public Hostname에 `fridge.chobihome.com → http://<LXC IP>:8080` 추가.
- 설정 파일로 관리하는 터널이면 `deploy/cloudflared-config.example.yml`의 ingress 항목을 기존 config에 붙이고 cloudflared 재시작.
- 이 경우 LXC 방화벽(또는 Proxmox 방화벽)으로 8080을 cloudflared가 도는 호스트에서만 열어 둔다.

## 5. Cloudflare Access (이메일 인증)

1. Zero Trust → **Access → Applications → Add an application → Self-hosted**
   - Application name: `냉장고 사전`
   - Application domain: `fridge.chobihome.com` (경로는 비워 둔다 → 전체 보호)
   - Session duration: **1 month** (주방 폰에서 매번 로그인하지 않게. 더 짧게 원하면 줄인다)
   - Identity providers: 기본 **One-time PIN**이면 이메일로 코드가 온다. Google을 붙여 두면 한 번 탭으로 끝난다.
2. **Add a policy**
   - Policy name `부부`, Action **Allow**
   - Include → Selector **Emails** → 두 사람 이메일을 넣는다.
3. 저장 후 폰에서 `https://fridge.chobihome.com` 접속 → 이메일 인증 → 화면이 뜨면 끝.

확인: `https://fridge.chobihome.com/api/state`를 각자 로그인한 폰에서 열면 사람마다 다른 `favs`가 보여야 한다. Access가 `Cf-Access-Authenticated-User-Email`을 붙여 주고 앱이 그걸로 사람을 나눈다.

## 6. MCP — claude.ai 커스텀 커넥터 (비밀 URL 방식)

사용자 결정(2026-10-22): 로그인 없는 비밀 URL. URL을 아는 쪽은 누구나 쓸 수 있으므로 아래 세 가지 보완을 같이 한다.

### 6-1. 비밀 만들고 켜기

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # 예: Qm3…(43자)
# .env 에 추가
MCP_SECRET=<위 값>
docker compose up -d
docker compose logs --tail 5 | grep mcp      # [mcp] 켜짐
curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8080/mcp/wrong   # 404
```

앱은 접근 로그를 끄고(`access_log=False`) 비밀 경로가 로그에 남지 않게 한다. 32자 미만이면 켜지지 않는다.

### 6-2. Cloudflare Access — `/mcp/*`만 Anthropic 서버에 열기

Claude의 호출은 Anthropic 서버에서 오므로 사람 로그인을 거칠 수 없다. `/mcp/*` 경로만 별도 애플리케이션으로 떼어 **Bypass**하되, **Anthropic 발신 IP 대역으로 제한**한다(공식 문서: `160.79.104.0/21`).

1. Zero Trust → **Access → Applications → Add an application → Self-hosted**
   - Application name: `냉장고 사전 MCP`
   - Application domain: subdomain `fridge`, domain `chobihome.com`, **path `mcp/*`** (경로 입력칸은 앞 `/` 없이)
   - Session duration: 상관없음(Bypass)
2. **Add a policy**: name `Anthropic 서버만`, Action **Bypass**, Include → **IP ranges** → `160.79.104.0/21`
3. 저장. Access는 더 구체적인 경로의 애플리케이션을 우선 적용하므로, 5절에서 만든 사이트 전체 애플리케이션(이메일 로그인)은 그대로 두면 된다.

확인:
- 집 PC에서 `curl -I https://fridge.chobihome.com/mcp/x` → Access 차단(403 또는 로그인 페이지). 집 IP는 대역 밖이라 정상이다.
- claude.ai에서 커넥터가 연결되면 Anthropic 대역에서 통과한 것이다.

Claude Code(내 PC)에서도 같은 서버를 쓰고 싶으면 IP 제한을 풀어야 한다(Include → Everyone). 그만큼 비밀 URL 하나에 기대게 되므로 권하지 않는다.

> 대역이 바뀌었는지는 https://platform.claude.com/docs/en/api/ip-addresses 에서 확인한다.

### 6-3. claude.ai에 커넥터 등록

1. claude.ai → **Customize → Connectors → Add custom connector**
2. 이름 `냉장고 사전`, **MCP server URL** `https://fridge.chobihome.com/mcp/<MCP_SECRET>`
3. Authentication: **No sign-in** → Add. (Request headers 칸이 보이면 그 조직은 베타가 열린 것이니 알려 주세요. 더 안전한 방식으로 바꿀 수 있습니다.)
4. 대화에서 **+ → Connectors**로 켜고 "냉장고 사전에 있는 레시피 목록 보여줘"로 확인. `list_recipes`가 24건 이상을 돌려주면 성공.
5. 테스트: "오늘 해 본 ○○ 레시피를 사전에 넣어줘" → 웹 화면에 바로 보이고, 하단 '최근 변경 이력'에 `claude.ai` 표시로 남고, '처음 버전으로/수정 전으로'로 되돌릴 수 있어야 한다.

### 6-4. 비밀이 샜을 때

`.env`의 `MCP_SECRET`을 새로 만들고 `docker compose up -d`. claude.ai 커넥터는 URL만 새 값으로 고친다(이름·URL은 수정 가능). 비밀은 URL에 들어 있어 Cloudflare Access 로그와 브라우저 기록에 남을 수 있으니 몇 달에 한 번 바꾸는 편이 좋다.

## 점검 목록

- [ ] `curl localhost:8080/api/health` → `{"ok":true}`
- [ ] 로그에 `[seed] recipe: 파일 24건`, `[seed] swap: 파일 21건`
- [ ] `https://fridge.chobihome.com` → Access 로그인 화면 → 앱
- [ ] 두 폰에서 즐겨찾기가 따로, 분량 배율과 식단 기록은 같이 보인다
- [ ] `db/` 백업이 cron으로 쌓인다
- [ ] `/mcp/x`가 집에서는 막히고(Access), claude.ai 커넥터는 연결된다
- [ ] claude.ai에서 넣은 테스트 레시피가 웹에 보이고 '최근 변경 이력'에서 되돌려진다
