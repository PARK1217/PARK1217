/* 냉장고 사전 서비스워커.
   역할은 두 가지뿐이다: (1) 타이머가 끝났을 때 알림을 띄울 수 있게 한다, (2) 홈 화면에 추가할 수 있게 한다.
   캐시는 하지 않는다. 데이터가 서버에 있으므로 오프라인 동작을 흉내 내지 않는다. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {});
self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    for (const c of list) { if ("focus" in c) return c.focus(); }
    return self.clients.openWindow("/");
  }));
});
