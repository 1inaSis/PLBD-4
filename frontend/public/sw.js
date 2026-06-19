// Service worker HealthGate — notifications push ESI 1/2 pour médecin

self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {}
  event.waitUntil(
    self.registration.showNotification(data.title ?? 'HealthGate', {
      body: data.body ?? '',
      icon: '/favicon.ico',
      tag: data.tag ?? 'healthgate',
      requireInteraction: true,
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(clients.openWindow('/'))
})
