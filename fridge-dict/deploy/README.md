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

## 6. 2단계(MCP) 때 바꿀 것 — 지금은 하지 않는다

- `/mcp` 경로만 Access에서 **Bypass** 정책을 가진 별도 애플리케이션(`fridge.chobihome.com/mcp`)으로 떼어내고, 앱 쪽에서 OAuth로 보호한다. claude.ai 커스텀 커넥터의 인증 요건을 문서로 확인한 뒤 승인받고 진행(CLAUDE.md 2단계 참고).

## 점검 목록

- [ ] `curl localhost:8080/api/health` → `{"ok":true}`
- [ ] 로그에 `[seed] recipe: 파일 24건`, `[seed] swap: 파일 21건`
- [ ] `https://fridge.chobihome.com` → Access 로그인 화면 → 앱
- [ ] 두 폰에서 즐겨찾기가 따로, 분량 배율과 식단 기록은 같이 보인다
- [ ] `db/` 백업이 cron으로 쌓인다
