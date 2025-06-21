// Service Worker with improved cache management and update handling
const APP_VERSION = '3.0.0';
const CACHE_VERSION = 'v3';
const STATIC_CACHE = `ham-radio-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `ham-radio-dynamic-${CACHE_VERSION}`;
const API_CACHE = `ham-radio-api-${CACHE_VERSION}`;

// Cache configuration
const CACHE_CONFIG = {
  maxAge: 24 * 60 * 60 * 1000, // 24 hours for dynamic content
  maxSize: 50, // Maximum number of items in dynamic cache
  maxApiAge: 5 * 60 * 1000, // 5 minutes for API responses
  maxApiSize: 20 // Maximum number of API responses to cache
};

// Files to cache immediately (critical resources)
const STATIC_FILES = [
  '/',
  '/static/manifest.json',
  '/offline.html',
  'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css'
];

// API endpoints to cache with their cache strategies
const API_ENDPOINTS = {
  '/api/spots': { strategy: 'network-first', maxAge: 2 * 60 * 1000 }, // 2 minutes
  '/api/spots/history': { strategy: 'cache-first', maxAge: 10 * 60 * 1000 }, // 10 minutes
  '/api/spots/status': { strategy: 'network-first', maxAge: 1 * 60 * 1000 }, // 1 minute
  '/api/conditions': { strategy: 'network-first', maxAge: 5 * 60 * 1000 } // 5 minutes
};

// Safari-specific detection
const isSafari = /^((?!chrome|android).)*safari/i.test(navigator.userAgent);

// Install event - cache static files and skip waiting
self.addEventListener('install', (event) => {
  console.log(`Service Worker installing... Version: ${APP_VERSION}`);
  event.waitUntil(
    Promise.all([
      cacheStaticFiles(),
      self.skipWaiting()
    ])
  );
});

// Activate event - clean up old caches and claim clients
self.addEventListener('activate', (event) => {
  console.log(`Service Worker activating... Version: ${APP_VERSION}`);
  event.waitUntil(
    Promise.all([
      cleanupOldCaches(),
      self.clients.claim()
    ])
  );
});

// Fetch event - handle requests with improved strategies
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Handle different types of requests
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(handleApiRequest(request));
  } else if (request.method === 'GET') {
    event.respondWith(handleStaticRequest(request));
  }
});

// Cache static files
async function cacheStaticFiles() {
  try {
    const cache = await caches.open(STATIC_CACHE);
    console.log('Caching static files...');
    
    const promises = STATIC_FILES.map(async (file) => {
      try {
        await cache.add(file);
        console.log(`Cached: ${file}`);
      } catch (error) {
        console.warn(`Failed to cache ${file}:`, error);
      }
    });
    
    await Promise.all(promises);
    console.log('Static files cached successfully');
  } catch (error) {
    console.error('Error caching static files:', error);
  }
}

// Clean up old caches
async function cleanupOldCaches() {
  try {
    const cacheNames = await caches.keys();
    const currentCaches = [STATIC_CACHE, DYNAMIC_CACHE, API_CACHE];
    
    const deletePromises = cacheNames
      .filter(cacheName => !currentCaches.includes(cacheName))
      .map(cacheName => {
        console.log(`Deleting old cache: ${cacheName}`);
        return caches.delete(cacheName);
      });
    
    await Promise.all(deletePromises);
    console.log('Old caches cleaned up');
  } catch (error) {
    console.error('Error cleaning up old caches:', error);
  }
}

// Handle API requests with configurable strategies
async function handleApiRequest(request) {
  const url = new URL(request.url);
  const endpoint = url.pathname;
  const config = API_ENDPOINTS[endpoint] || { strategy: 'network-first', maxAge: CACHE_CONFIG.maxApiAge };
  
  switch (config.strategy) {
    case 'network-first':
      return handleNetworkFirst(request, config.maxAge, API_CACHE);
    case 'cache-first':
      return handleCacheFirst(request, config.maxAge, API_CACHE);
    case 'stale-while-revalidate':
      return handleStaleWhileRevalidate(request, config.maxAge, API_CACHE);
    default:
      return handleNetworkFirst(request, config.maxAge, API_CACHE);
  }
}

// Network-first strategy
async function handleNetworkFirst(request, maxAge, cacheName) {
  try {
    // Try network first
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      // Cache the response
      const cache = await caches.open(cacheName);
      const responseToCache = networkResponse.clone();
      
      // Add cache metadata
      const metadata = {
        timestamp: Date.now(),
        maxAge: maxAge,
        url: request.url
      };
      
      const responseWithMetadata = new Response(responseToCache.body, {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers: {
          ...Object.fromEntries(responseToCache.headers.entries()),
          'sw-cache-timestamp': metadata.timestamp.toString(),
          'sw-cache-max-age': metadata.maxAge.toString()
        }
      });
      
      await cache.put(request, responseWithMetadata);
      await cleanupCache(cacheName, CACHE_CONFIG.maxApiSize);
      
      return networkResponse;
    }
  } catch (error) {
    console.log('Network failed, trying cache for:', request.url);
  }
  
  // Fall back to cache
  const cachedResponse = await getValidCachedResponse(request, maxAge, cacheName);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  // Return offline response
  return new Response(
    JSON.stringify({
      error: 'Offline - No cached data available',
      offline: true,
      timestamp: Date.now()
    }),
    {
      status: 503,
      statusText: 'Service Unavailable',
      headers: { 'Content-Type': 'application/json' }
    }
  );
}

// Cache-first strategy
async function handleCacheFirst(request, maxAge, cacheName) {
  // Try cache first
  const cachedResponse = await getValidCachedResponse(request, maxAge, cacheName);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    // Fall back to network
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      const responseToCache = networkResponse.clone();
      
      const metadata = {
        timestamp: Date.now(),
        maxAge: maxAge,
        url: request.url
      };
      
      const responseWithMetadata = new Response(responseToCache.body, {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers: {
          ...Object.fromEntries(responseToCache.headers.entries()),
          'sw-cache-timestamp': metadata.timestamp.toString(),
          'sw-cache-max-age': metadata.maxAge.toString()
        }
      });
      
      await cache.put(request, responseWithMetadata);
      await cleanupCache(cacheName, CACHE_CONFIG.maxApiSize);
    }
    
    return networkResponse;
  } catch (error) {
    console.error('Network failed for cache-first request:', request.url);
    throw error;
  }
}

// Stale-while-revalidate strategy
async function handleStaleWhileRevalidate(request, maxAge, cacheName) {
  const cachedResponse = await getValidCachedResponse(request, maxAge, cacheName);
  
  // Return cached response immediately if available
  if (cachedResponse) {
    // Update cache in background
    fetch(request).then(async (networkResponse) => {
      if (networkResponse.ok) {
        const cache = await caches.open(cacheName);
        const responseToCache = networkResponse.clone();
        
        const metadata = {
          timestamp: Date.now(),
          maxAge: maxAge,
          url: request.url
        };
        
        const responseWithMetadata = new Response(responseToCache.body, {
          status: responseToCache.status,
          statusText: responseToCache.statusText,
          headers: {
            ...Object.fromEntries(responseToCache.headers.entries()),
            'sw-cache-timestamp': metadata.timestamp.toString(),
            'sw-cache-max-age': metadata.maxAge.toString()
          }
        });
        
        await cache.put(request, responseWithMetadata);
        await cleanupCache(cacheName, CACHE_CONFIG.maxApiSize);
      }
    }).catch(error => {
      console.log('Background update failed:', error);
    });
    
    return cachedResponse;
  }
  
  // If no cache, try network
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      const responseToCache = networkResponse.clone();
      
      const metadata = {
        timestamp: Date.now(),
        maxAge: maxAge,
        url: request.url
      };
      
      const responseWithMetadata = new Response(responseToCache.body, {
        status: responseToCache.status,
        statusText: responseToCache.statusText,
        headers: {
          ...Object.fromEntries(responseToCache.headers.entries()),
          'sw-cache-timestamp': metadata.timestamp.toString(),
          'sw-cache-max-age': metadata.maxAge.toString()
        }
      });
      
      await cache.put(request, responseWithMetadata);
      await cleanupCache(cacheName, CACHE_CONFIG.maxApiSize);
    }
    
    return networkResponse;
  } catch (error) {
    console.error('Network failed for stale-while-revalidate request:', request.url);
    throw error;
  }
}

// Get valid cached response (not expired)
async function getValidCachedResponse(request, maxAge, cacheName) {
  try {
    const cache = await caches.open(cacheName);
    const response = await cache.match(request);
    
    if (response) {
      const timestamp = response.headers.get('sw-cache-timestamp');
      const cacheMaxAge = response.headers.get('sw-cache-max-age');
      
      if (timestamp && cacheMaxAge) {
        const age = Date.now() - parseInt(timestamp);
        const maxAgeMs = parseInt(cacheMaxAge);
        
        if (age < maxAgeMs) {
          return response;
        } else {
          // Remove expired cache entry
          await cache.delete(request);
        }
      }
    }
  } catch (error) {
    console.error('Error getting cached response:', error);
  }
  
  return null;
}

// Clean up cache to maintain size limits
async function cleanupCache(cacheName, maxSize) {
  try {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    
    if (keys.length > maxSize) {
      // Get cache entries with their timestamps
      const entries = await Promise.all(
        keys.map(async (key) => {
          const response = await cache.match(key);
          const timestamp = response?.headers.get('sw-cache-timestamp') || '0';
          return { key, timestamp: parseInt(timestamp) };
        })
      );
      
      // Sort by timestamp (oldest first)
      entries.sort((a, b) => a.timestamp - b.timestamp);
      
      // Remove oldest entries
      const toDelete = entries.slice(0, entries.length - maxSize);
      await Promise.all(toDelete.map(entry => cache.delete(entry.key)));
      
      console.log(`Cleaned up ${toDelete.length} old cache entries from ${cacheName}`);
    }
  } catch (error) {
    console.error('Error cleaning up cache:', error);
  }
}

// Handle static file requests with cache-first strategy
async function handleStaticRequest(request) {
  const cachedResponse = await caches.match(request);
  
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(STATIC_CACHE);
      await cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('Network failed for static file:', request.url);
    
    // Return offline page for HTML requests
    if (request.headers.get('accept')?.includes('text/html')) {
      return caches.match('/offline.html');
    }
    
    throw error;
  }
}

// Message handling for updates and cache management
self.addEventListener('message', (event) => {
  const { data } = event;
  
  switch (data?.type) {
    case 'SKIP_WAITING':
      console.log('Skip waiting message received');
      self.skipWaiting();
      break;
      
    case 'FORCE_REFRESH':
      console.log('Force refresh message received');
      event.waitUntil(
        self.clients.matchAll().then((clients) => {
          clients.forEach((client) => {
            client.postMessage({ type: 'FORCE_REFRESH' });
          });
        })
      );
      break;
      
    case 'CLEAR_CACHE':
      console.log('Clear cache message received');
      event.waitUntil(clearAllCaches());
      break;
      
    case 'UPDATE_AVAILABLE':
      console.log('Update available message received');
      event.waitUntil(
        self.clients.matchAll().then((clients) => {
          clients.forEach((client) => {
            client.postMessage({ 
              type: 'UPDATE_AVAILABLE',
              version: data.version 
            });
          });
        })
      );
      break;
  }
});

// Clear all caches
async function clearAllCaches() {
  try {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map(name => caches.delete(name)));
    console.log('All caches cleared');
  } catch (error) {
    console.error('Error clearing caches:', error);
  }
}

// Background sync for updating data
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    console.log('Background sync triggered');
    event.waitUntil(updateCachedData());
  }
});

// Update cached data in background
async function updateCachedData() {
  try {
    const cache = await caches.open(API_CACHE);
    
    // Update API endpoints
    for (const [endpoint, config] of Object.entries(API_ENDPOINTS)) {
      try {
        const response = await fetch(endpoint);
        if (response.ok) {
          const responseToCache = response.clone();
          
          const metadata = {
            timestamp: Date.now(),
            maxAge: config.maxAge,
            url: endpoint
          };
          
          const responseWithMetadata = new Response(responseToCache.body, {
            status: responseToCache.status,
            statusText: responseToCache.statusText,
            headers: {
              ...Object.fromEntries(responseToCache.headers.entries()),
              'sw-cache-timestamp': metadata.timestamp.toString(),
              'sw-cache-max-age': metadata.maxAge.toString()
            }
          });
          
          await cache.put(endpoint, responseWithMetadata);
        }
      } catch (error) {
        console.log('Failed to update cached data for:', endpoint);
      }
    }
    
    await cleanupCache(API_CACHE, CACHE_CONFIG.maxApiSize);
    console.log('Background data update completed');
  } catch (error) {
    console.error('Background sync failed:', error);
  }
}

// Push notification handling
self.addEventListener('push', (event) => {
  console.log('Push notification received');
  
  const options = {
    body: event.data ? event.data.text() : 'New ham radio conditions available',
    icon: '/static/icons/icon-192x192.png',
    badge: '/static/icons/icon-72x72.png',
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'View Conditions',
        icon: '/static/icons/icon-72x72.png'
      },
      {
        action: 'close',
        title: 'Close',
        icon: '/static/icons/icon-72x72.png'
      }
    ]
  };
  
  event.waitUntil(
    self.registration.showNotification('Ham Radio Conditions', options)
  );
});

// Notification click handling
self.addEventListener('notificationclick', (event) => {
  console.log('Notification clicked');
  
  event.notification.close();
  
  if (event.action === 'explore') {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
}); 