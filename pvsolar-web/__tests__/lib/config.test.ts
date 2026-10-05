import { config } from '@/lib/config';

describe('Config', () => {
  it('has all service URLs', () => {
    expect(config.gateway).toBeDefined();
    expect(config.analytics).toBeDefined();
    expect(config.scada).toBeDefined();
    expect(config.reports).toBeDefined();
    expect(config.fleet).toBeDefined();
    expect(config.alert).toBeDefined();
    expect(config.grid).toBeDefined();
    expect(config.twin).toBeDefined();
    expect(config.auth).toBeDefined();
  });

  it('has default port values', () => {
    expect(config.gateway).toContain('8000');
    expect(config.analytics).toContain('8001');
    expect(config.auth).toContain('8007');
  });
});
