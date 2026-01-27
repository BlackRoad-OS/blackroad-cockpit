/**
 * BlackRoad State Worker
 * =====================
 *
 * Cloudflare Worker for managing distributed state.
 * Provides REST API for state operations.
 *
 * Deploy to Cloudflare Workers with KV namespace binding.
 *
 * KV Bindings:
 *   - BLACKROAD_STATE: Main state storage
 *
 * Environment Variables:
 *   - API_SECRET: Shared secret for authentication
 */

// CORS headers
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
};

// Response helpers
const jsonResponse = (data, status = 200) => {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...corsHeaders,
    },
  });
};

const errorResponse = (message, status = 400) => {
  return jsonResponse({ error: message }, status);
};

// Authentication
const authenticate = (request, env) => {
  const apiKey = request.headers.get('X-API-Key');
  const authHeader = request.headers.get('Authorization');

  if (apiKey && apiKey === env.API_SECRET) {
    return true;
  }

  if (authHeader && authHeader.startsWith('Bearer ')) {
    const token = authHeader.slice(7);
    return token === env.API_SECRET;
  }

  return false;
};

// Main handler
export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    const url = new URL(request.url);
    const path = url.pathname;

    // Health check (no auth required)
    if (path === '/health' || path === '/') {
      return jsonResponse({
        status: 'healthy',
        service: 'blackroad-state-worker',
        timestamp: new Date().toISOString(),
      });
    }

    // Authenticate all other requests
    if (!authenticate(request, env)) {
      return errorResponse('Unauthorized', 401);
    }

    // Route handling
    try {
      // GET /state/:key - Get a state record
      if (request.method === 'GET' && path.startsWith('/state/')) {
        const key = path.slice(7);
        const value = await env.BLACKROAD_STATE.get(key, 'json');

        if (value) {
          return jsonResponse(value);
        }
        return errorResponse('Not found', 404);
      }

      // GET /state - List all state records
      if (request.method === 'GET' && path === '/state') {
        const prefix = url.searchParams.get('prefix') || '';
        const limit = parseInt(url.searchParams.get('limit') || '100');

        const list = await env.BLACKROAD_STATE.list({ prefix, limit });
        const records = [];

        for (const key of list.keys) {
          const value = await env.BLACKROAD_STATE.get(key.name, 'json');
          if (value) {
            records.push(value);
          }
        }

        return jsonResponse({
          records,
          count: records.length,
          cursor: list.cursor,
        });
      }

      // PUT /state/:key - Store a state record
      if (request.method === 'PUT' && path.startsWith('/state/')) {
        const key = path.slice(7);
        const body = await request.json();

        // Add metadata
        body.updated_at = Date.now() / 1000;
        body.cloudflare_key = key;

        await env.BLACKROAD_STATE.put(key, JSON.stringify(body));

        return jsonResponse({
          success: true,
          key,
          updated_at: body.updated_at,
        });
      }

      // POST /state - Create a new state record
      if (request.method === 'POST' && path === '/state') {
        const body = await request.json();

        // Generate key if not provided
        const key = body.cloudflare_key ||
          `${body.entity_type || 'task'}:${body.id || crypto.randomUUID().slice(0, 8)}`;

        body.cloudflare_key = key;
        body.created_at = body.created_at || Date.now() / 1000;
        body.updated_at = Date.now() / 1000;

        await env.BLACKROAD_STATE.put(key, JSON.stringify(body));

        return jsonResponse({
          success: true,
          key,
          record: body,
        }, 201);
      }

      // DELETE /state/:key - Delete a state record
      if (request.method === 'DELETE' && path.startsWith('/state/')) {
        const key = path.slice(7);

        await env.BLACKROAD_STATE.delete(key);

        return jsonResponse({
          success: true,
          key,
          deleted: true,
        });
      }

      // POST /sync - Trigger state sync
      if (request.method === 'POST' && path === '/sync') {
        const body = await request.json();
        const records = body.records || [];
        const results = [];

        for (const record of records) {
          const key = record.cloudflare_key ||
            `${record.entity_type}:${record.id}`;

          record.cloudflare_key = key;
          record.updated_at = Date.now() / 1000;

          await env.BLACKROAD_STATE.put(key, JSON.stringify(record));
          results.push({ key, success: true });
        }

        return jsonResponse({
          synced: results.length,
          results,
          timestamp: new Date().toISOString(),
        });
      }

      // POST /webhook/github - GitHub webhook handler
      if (request.method === 'POST' && path === '/webhook/github') {
        const body = await request.json();
        const event = request.headers.get('X-GitHub-Event');

        let stateUpdate = null;

        // Handle different GitHub events
        switch (event) {
          case 'issues':
            stateUpdate = {
              entity_type: 'task',
              id: `issue-${body.issue.number}`,
              name: body.issue.title,
              status: body.action === 'closed' ? 'done' : 'todo',
              github_ref: `#${body.issue.number}`,
              metadata: {
                labels: body.issue.labels.map(l => l.name),
                assignee: body.issue.assignee?.login,
              },
            };
            break;

          case 'pull_request':
            const prStatus = {
              opened: 'code_review',
              closed: body.pull_request.merged ? 'done' : 'backlog',
              review_requested: 'code_review',
            }[body.action] || 'in_progress';

            stateUpdate = {
              entity_type: 'task',
              id: `pr-${body.pull_request.number}`,
              name: body.pull_request.title,
              status: prStatus,
              github_ref: `#${body.pull_request.number}`,
              metadata: {
                draft: body.pull_request.draft,
                merged: body.pull_request.merged,
                author: body.pull_request.user.login,
              },
            };
            break;

          case 'deployment':
            stateUpdate = {
              entity_type: 'deployment',
              id: `deploy-${body.deployment.id}`,
              name: `Deploy ${body.deployment.ref}`,
              status: body.deployment.task === 'deploy' ? 'staging' : 'done',
              metadata: {
                environment: body.deployment.environment,
                ref: body.deployment.ref,
              },
            };
            break;
        }

        if (stateUpdate) {
          const key = `${stateUpdate.entity_type}:${stateUpdate.id}`;
          stateUpdate.cloudflare_key = key;
          stateUpdate.updated_at = Date.now() / 1000;

          await env.BLACKROAD_STATE.put(key, JSON.stringify(stateUpdate));

          return jsonResponse({
            success: true,
            event,
            key,
          });
        }

        return jsonResponse({
          success: true,
          event,
          message: 'Event acknowledged but no state update needed',
        });
      }

      // GET /stats - Get state statistics
      if (request.method === 'GET' && path === '/stats') {
        const list = await env.BLACKROAD_STATE.list({ limit: 1000 });

        const stats = {
          total: list.keys.length,
          by_type: {},
          by_status: {},
        };

        for (const key of list.keys) {
          const value = await env.BLACKROAD_STATE.get(key.name, 'json');
          if (value) {
            stats.by_type[value.entity_type] =
              (stats.by_type[value.entity_type] || 0) + 1;
            stats.by_status[value.status] =
              (stats.by_status[value.status] || 0) + 1;
          }
        }

        return jsonResponse(stats);
      }

      return errorResponse('Not found', 404);

    } catch (error) {
      console.error('Worker error:', error);
      return errorResponse(`Internal error: ${error.message}`, 500);
    }
  },
};
