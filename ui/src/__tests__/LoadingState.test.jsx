import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { LoadingState } from '../components/LoadingState';

describe('LoadingState Component', () => {
  it('renders loading spinner', () => {
    const { container } = render(<LoadingState />);

    // Check if Ant Design Spin component is rendered
    const spinner = container.querySelector('.ant-spin');
    expect(spinner).toBeInTheDocument();
    expect(spinner).toHaveClass('ant-spin-spinning');
  });
});
