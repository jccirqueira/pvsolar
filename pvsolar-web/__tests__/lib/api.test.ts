import { gatewayApi } from '@/lib/api';

describe('ApiClient', () => {
  const fetchMock = jest.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    (global as unknown as { fetch: unknown }).fetch = fetchMock;
    gatewayApi.setToken(null);
  });

  const okJson = (data: unknown) =>
    Promise.resolve({
      ok: true,
      status: 200,
      text: () => Promise.resolve(JSON.stringify(data)),
      json: () => Promise.resolve(data),
    } as unknown as Response);

  const okEmpty = () =>
    Promise.resolve({
      ok: true,
      status: 200,
      text: () => Promise.resolve(''),
    } as unknown as Response);

  const httpError = (status: number, statusText: string, body: unknown, jsonFails = false) =>
    Promise.resolve({
      ok: false,
      status,
      statusText,
      json: jsonFails
        ? () => Promise.reject(new Error('nao e JSON'))
        : () => Promise.resolve(body),
    } as unknown as Response);

  it('get: busca JSON com Content-Type e cache no-store', async () => {
    fetchMock.mockReturnValue(okJson({ valor: 1 }));
    const res = await gatewayApi.get<{ valor: number }>('/api/x');
    expect(res).toEqual({ valor: 1 });

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
    expect(url).toContain('/api/x');
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.headers.Authorization).toBeUndefined();
    expect(init.cache).toBe('no-store');
  });

  it('get: corpo vazio retorna null', async () => {
    fetchMock.mockReturnValue(okEmpty());
    await expect(gatewayApi.get('/api/vazio')).resolves.toBeNull();
  });

  it('setToken: inclui Authorization Bearer quando ha token', async () => {
    gatewayApi.setToken('tok123');
    fetchMock.mockReturnValue(okJson({}));
    await gatewayApi.get('/api/y');
    const [, init] = fetchMock.mock.calls[0] as [string, { headers: Record<string, string> }];
    expect(init.headers.Authorization).toBe('Bearer tok123');
  });

  it('setToken(null): remove o Authorization', async () => {
    gatewayApi.setToken('tok123');
    gatewayApi.setToken(null);
    fetchMock.mockReturnValue(okJson({}));
    await gatewayApi.get('/api/y');
    const [, init] = fetchMock.mock.calls[0] as [string, { headers: Record<string, string> }];
    expect(init.headers.Authorization).toBeUndefined();
  });

  it('get: erro da API usa detail e expoe status', async () => {
    fetchMock.mockReturnValue(httpError(404, 'Not Found', { detail: 'recurso nao existe' }));
    let erro: (Error & { status?: number }) | undefined;
    try {
      await gatewayApi.get('/api/404');
    } catch (e) {
      erro = e as Error & { status?: number };
    }
    expect(erro).toBeDefined();
    expect(erro?.message).toBe('404: recurso nao existe');
    expect(erro?.status).toBe(404);
  });

  it('get: erro da API sem detail usa message', async () => {
    fetchMock.mockReturnValue(httpError(400, 'Bad Request', { message: 'entrada invalida' }));
    await expect(gatewayApi.get('/api/400')).rejects.toThrow('400: entrada invalida');
  });

  it('get: erro sem detail nem message serializa o corpo', async () => {
    fetchMock.mockReturnValue(httpError(422, 'Unprocessable', { campo: 'x' }));
    await expect(gatewayApi.get('/api/422')).rejects.toThrow('422: {"campo":"x"}');
  });

  it('get: corpo de erro nao-JSON cai no statusText', async () => {
    fetchMock.mockReturnValue(httpError(500, 'Internal Server Error', null, true));
    await expect(gatewayApi.get('/api/500')).rejects.toThrow('500: Internal Server Error');
  });

  it('get: falha de conexao tem mensagem propria', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(gatewayApi.get('/api/off')).rejects.toThrow(
      'Falha de conexao com'
    );
  });

  it('post: envia method POST e corpo JSON serializado', async () => {
    fetchMock.mockReturnValue(okJson({ criado: true }));
    const res = await gatewayApi.post<{ criado: boolean }>('/api/itens', { nome: 'a' });
    expect(res).toEqual({ criado: true });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('POST');
    expect(init.body).toBe(JSON.stringify({ nome: 'a' }));
  });

  it('post: falha de conexao tem mensagem propria', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(gatewayApi.post('/api/itens', {})).rejects.toThrow('Falha de conexao com');
  });

  it('put: envia method PUT e corpo JSON', async () => {
    fetchMock.mockReturnValue(okJson({ atualizado: true }));
    await gatewayApi.put('/api/itens/1', { nome: 'b' });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('PUT');
    expect(init.body).toBe(JSON.stringify({ nome: 'b' }));
  });

  it('put: falha de conexao tem mensagem propria', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(gatewayApi.put('/api/itens/1', {})).rejects.toThrow('Falha de conexao com');
  });

  it('delete: envia method DELETE', async () => {
    fetchMock.mockReturnValue(okJson({ removido: true }));
    await gatewayApi.delete('/api/itens/1');
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe('DELETE');
  });

  it('delete: falha de conexao tem mensagem propria', async () => {
    fetchMock.mockRejectedValue(new Error('ECONNREFUSED'));
    await expect(gatewayApi.delete('/api/itens/1')).rejects.toThrow('Falha de conexao com');
  });

  it('delete: erro da API propaga mensagem e status', async () => {
    fetchMock.mockReturnValue(httpError(403, 'Forbidden', { detail: 'sem permissao' }));
    let erro: (Error & { status?: number }) | undefined;
    try {
      await gatewayApi.delete('/api/itens/1');
    } catch (e) {
      erro = e as Error & { status?: number };
    }
    expect(erro?.message).toBe('403: sem permissao');
    expect(erro?.status).toBe(403);
  });
});
