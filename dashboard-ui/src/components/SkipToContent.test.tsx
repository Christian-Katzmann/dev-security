import {render, screen} from '@testing-library/react';
import {axe} from 'jest-axe';
import {describe, expect, it} from 'vitest';
import SkipToContent from './SkipToContent';

describe('SkipToContent (S-045)', () => {
  it('renders a "Skip to content" link pointing at the main region', () => {
    render(<SkipToContent />);
    const link = screen.getByRole('link', {name: 'Skip to content'});
    expect(link).toHaveAttribute('href', '#main-content');
    expect(link).toHaveClass('skip-link');
  });

  it('has no axe violations', async () => {
    const {container} = render(<SkipToContent />);
    expect(await axe(container)).toHaveNoViolations();
  });
});
