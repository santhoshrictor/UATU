/** Keep the no-login development token endpoint restricted to loopback origins. */
export function sameOrigin(request: Request): boolean {
  try {
    const originHeader = request.headers.get('origin');
    if (!originHeader) {
      // Local development non-browser or direct loopback requests
      return true;
    }
    const origin = new URL(originHeader);
    const isLoopback = ['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname);
    if (!isLoopback) {
      return false;
    }
    // Allow loopback ports 3000 (HUD console), 5173 (UATU Vite dashboard), 8000 (FastAPI) or same host
    return (
      ['3000', '5173', '8000'].includes(origin.port) ||
      origin.host === request.headers.get('host')
    );
  } catch {
    return false;
  }
}

