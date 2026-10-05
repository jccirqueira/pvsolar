/**
 * Testes do ThemeContext (tema claro/escuro).
 * @jest-environment jsdom
 */
import { render, act, waitFor } from '@testing-library/react';
import { ThemeProvider, useTheme } from '@/contexts/ThemeContext';

// Coletor de valores expostos pelo hook
let captured: { theme: string; toggleTheme: () => void; setTheme: (t: 'light' | 'dark') => void };

function Probe() {
  captured = useTheme();
  return null;
}

function renderTheme() {
  return render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove('dark');
  document.documentElement.style.colorScheme = '';
});

describe('ThemeContext', () => {
  it('inicia no tema claro por padrao', async () => {
    renderTheme();
    await waitFor(() => expect(captured).toBeDefined());
    expect(captured.theme).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('alterna para escuro e aplica a classe no <html>', async () => {
    renderTheme();
    await waitFor(() => expect(captured).toBeDefined());

    act(() => captured.toggleTheme());

    expect(captured.theme).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('persiste a escolha no localStorage', async () => {
    renderTheme();
    await waitFor(() => expect(captured).toBeDefined());

    act(() => captured.toggleTheme());

    expect(localStorage.getItem('pvsolar_theme')).toBe('dark');
  });

  it('alterna de volta para claro', async () => {
    renderTheme();
    await waitFor(() => expect(captured).toBeDefined());

    act(() => captured.toggleTheme());
    expect(captured.theme).toBe('dark');

    act(() => captured.toggleTheme());
    expect(captured.theme).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('pvsolar_theme')).toBe('light');
  });

  it('setTheme define um tema especifico', async () => {
    renderTheme();
    await waitFor(() => expect(captured).toBeDefined());

    act(() => captured.setTheme('dark'));
    expect(captured.theme).toBe('dark');
    expect(localStorage.getItem('pvsolar_theme')).toBe('dark');

    act(() => captured.setTheme('light'));
    expect(captured.theme).toBe('light');
  });

  it('restaura o tema salvo na montagem', async () => {
    localStorage.setItem('pvsolar_theme', 'dark');
    renderTheme();
    await waitFor(() => expect(captured.theme).toBe('dark'));
    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('lanca erro fora do ThemeProvider', () => {
    const spy = jest.spyOn(console, 'error').mockImplementation(() => {});
    function Orphan() {
      useTheme();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow('useTheme must be used within ThemeProvider');
    spy.mockRestore();
  });
});
