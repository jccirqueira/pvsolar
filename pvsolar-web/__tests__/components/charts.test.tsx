import { render, screen } from '@testing-library/react';
import PowerChart from '@/components/charts/PowerChart';
import EnergyChart from '@/components/charts/EnergyChart';
import DonutChart from '@/components/charts/DonutChart';
import { ThemeProvider } from '@/contexts/ThemeContext';

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: any) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }: any) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  Legend: () => null,
  BarChart: ({ children }: any) => <div>{children}</div>,
  Bar: () => null,
  PieChart: ({ children }: any) => <div>{children}</div>,
  Pie: () => null,
  Cell: () => null,
}));

// Os graficos usam useTheme() para adaptar cores ao tema atual.
function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('PowerChart', () => {
  it('renders chart container', () => {
    renderWithTheme(<PowerChart data={[{ timestamp: '2024-01-01', value: 100, label: '10:00' }]} />);
    expect(screen.getByTestId('chart')).toBeDefined();
  });

  it('renders title when provided', () => {
    renderWithTheme(<PowerChart data={[]} title="Potencia em tempo real" />);
    expect(screen.getByText('Potencia em tempo real')).toBeDefined();
  });
});

describe('EnergyChart', () => {
  it('renders chart container', () => {
    renderWithTheme(<EnergyChart data={[{ label: 'Hoje', expected: 100, actual: 90 }]} />);
    expect(screen.getByTestId('chart')).toBeDefined();
  });

  it('renders title when provided', () => {
    renderWithTheme(<EnergyChart data={[]} title="Energia diaria" />);
    expect(screen.getByText('Energia diaria')).toBeDefined();
  });
});

describe('DonutChart', () => {
  it('renders chart container', () => {
    renderWithTheme(<DonutChart data={[{ name: 'Online', value: 5, color: '#10b981' }]} />);
    expect(screen.getByTestId('chart')).toBeDefined();
  });

  it('renders center label/value when provided', () => {
    renderWithTheme(
      <DonutChart data={[{ name: 'Online', value: 5, color: '#10b981' }]} centerLabel="Inversores" centerValue="5" />
    );
    expect(screen.getByText('Inversores')).toBeDefined();
    expect(screen.getByText('5')).toBeDefined();
  });
});
