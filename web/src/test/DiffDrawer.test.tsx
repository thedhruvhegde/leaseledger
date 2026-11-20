import { fireEvent, render, screen, within } from '@testing-library/react';
import { DiffDrawer } from '../components/DiffDrawer';
import type { DiffResult, Listing } from '../types';
import { MOCK_LISTINGS } from '../api/mockData';

const names = new Map<string, Listing>(MOCK_LISTINGS.map((l) => [l.id, l]));
const diff: DiffResult = {
  rank_changes: [
    { listing_id: 'syn-packard-room', before: 2, after: 1 },
    { listing_id: 'syn-kerrytown-room', before: 1, after: 2 },
    { listing_id: 'syn-state-loft', before: null, after: null },
  ],
  deltas: {
    'syn-packard-room': { cash: 8, time_h: -3.3, late_night: -60, all_in: -210 },
    'syn-kerrytown-room': { cash: 8, time_h: -3, late_night: -47, all_in: -193 },
    'syn-state-loft': { cash: 0, time_h: 0, late_night: 0, all_in: 0 },
  },
  causes: ['Travel modes: walk + bus → walk + bus + bike.', 'New #1: syn-packard-room (was #2).'],
  top_changed: true,
};

describe('DiffDrawer', () => {
  it('shows the headline, humanized causes, deltas and rank moves', () => {
    render(<DiffDrawer diff={diff} names={names} open pinned={false} onClose={() => {}} onPin={() => {}} onUnpin={() => {}} />);
    expect(screen.getByTestId('diff-headline')).toHaveTextContent('Your #1 changed.');
    expect(screen.getByText(/New #1: Packard St room \(lowest rent\) \(was #2\)/)).toBeInTheDocument();
    const rows = screen.getAllByTestId('diff-row');
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByText(/Packard St room/)).toBeInTheDocument();
    expect(within(rows[0]).getByText('−$210 all-in')).toBeInTheDocument();
    expect(within(rows[0]).getByLabelText('Rank up from 2 to 1')).toBeInTheDocument();
  });
  it('toggles to the before snapshot ordering', () => {
    render(<DiffDrawer diff={diff} names={names} open pinned={false} onClose={() => {}} onPin={() => {}} onUnpin={() => {}} />);
    fireEvent.click(screen.getByRole('radio', { name: 'Before' }));
    const rows = screen.getAllByTestId('diff-row');
    expect(within(rows[0]).getByText(/Kerrytown room/)).toBeInTheDocument();
  });
  it('pins and closes', () => {
    const onPin = vi.fn();
    const onClose = vi.fn();
    render(<DiffDrawer diff={diff} names={names} open pinned={false} onClose={onClose} onPin={onPin} onUnpin={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /Pin now/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Close what changed' }));
    expect(onPin).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });
  it('renders nothing when closed', () => {
    const { container } = render(<DiffDrawer diff={diff} names={names} open={false} pinned={false} onClose={() => {}} onPin={() => {}} onUnpin={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
