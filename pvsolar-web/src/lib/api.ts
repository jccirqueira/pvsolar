import { config } from './config';

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    return headers;
  }

  private async handleResponse(res: Response): Promise<any> {
    if (res.ok) {
      const text = await res.text();
      return text ? JSON.parse(text) : null;
    }
    // Extrai a mensagem de erro da API
    let detail = '';
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch {
      detail = res.statusText;
    }
    const err = new Error(`${res.status}: ${detail}`) as Error & { status: number };
    err.status = res.status;
    throw err;
  }

  async get<T>(path: string): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        headers: this.getHeaders(),
        cache: 'no-store',
      });
    } catch (e) {
      throw new Error(`Falha de conexao com ${this.baseUrl}`);
    }
    return this.handleResponse(res);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      });
    } catch (e) {
      throw new Error(`Falha de conexao com ${this.baseUrl}`);
    }
    return this.handleResponse(res);
  }

  async put<T>(path: string, body: unknown): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'PUT',
        headers: this.getHeaders(),
        body: JSON.stringify(body),
      });
    } catch (e) {
      throw new Error(`Falha de conexao com ${this.baseUrl}`);
    }
    return this.handleResponse(res);
  }

  async delete<T>(path: string): Promise<T> {
    let res: Response;
    try {
      res = await fetch(`${this.baseUrl}${path}`, {
        method: 'DELETE',
        headers: this.getHeaders(),
      });
    } catch (e) {
      throw new Error(`Falha de conexao com ${this.baseUrl}`);
    }
    return this.handleResponse(res);
  }
}

export const gatewayApi = new ApiClient(config.gateway);
export const analyticsApi = new ApiClient(config.analytics);
export const scadaApi = new ApiClient(config.scada);
export const reportsApi = new ApiClient(config.reports);
export const fleetApi = new ApiClient(config.fleet);
export const alertApi = new ApiClient(config.alert);
export const gridApi = new ApiClient(config.grid);
export const twinApi = new ApiClient(config.twin);
export const authApi = new ApiClient(config.auth);
