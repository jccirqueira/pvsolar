import { render, screen } from '@testing-library/react';
import StatusCard from '@/components/ui/StatusCard';
import Badge from '@/components/ui/Badge';
import Card from '@/components/ui/Card';

describe('StatusCard', () => {
  it('renders title and value', () => {
    render(<StatusCard title="Potencia" value="100 kW" icon={<span>icon</span>} color="green" />);
    expect(screen.getByText('Potencia')).toBeDefined();
    expect(screen.getByText('100 kW')).toBeDefined();
  });

  it('renders subtitle when provided', () => {
    render(<StatusCard title="Title" value="Val" icon={<span>icon</span>} color="blue" subtitle="Sub" />);
    expect(screen.getByText('Sub')).toBeDefined();
  });
});

describe('Badge', () => {
  it('renders children', () => {
    render(<Badge variant="success">Online</Badge>);
    expect(screen.getByText('Online')).toBeDefined();
  });
});

describe('Card', () => {
  it('renders title and children', () => {
    render(<Card title="Test Card"><div>Content</div></Card>);
    expect(screen.getByText('Test Card')).toBeDefined();
    expect(screen.getByText('Content')).toBeDefined();
  });
});
