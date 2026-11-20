import { fireEvent, render, screen } from '@testing-library/react';
import { WeeklyGrid, applyDrag } from '../components/WeeklyGrid';
import { MOCK_BUILDINGS } from '../api/mockData';
import type { Event } from '../types';

const bmap = new Map(MOCK_BUILDINGS.map((b) => [b.id, b]));
const lab: Event = { label: 'Lab', building_id: 'ggbrown', point: null, days: ['T'], start_min: 540, end_min: 720, fixed: true, source_quote: 'lab Tuesday 9 to noon in GG Brown', provenance: 'estimated' };
const lec: Event = { label: 'Lecture', building_id: 'bbb', point: null, days: ['M', 'W', 'F'], start_min: 540, end_min: 630, fixed: true, provenance: 'user' };

describe('applyDrag', () => {
  it('snaps moves to 15 minutes and keeps duration', () => {
    expect(applyDrag(lab, 'move', -58, 'T', 'T')).toEqual({ start_min: 480, end_min: 660 });
  });
  it('moves a block to another day', () => {
    expect(applyDrag(lab, 'move', 0, 'T', 'R').days).toEqual(['R']);
  });
  it('resizes but never below one snap step', () => {
    expect(applyDrag(lab, 'resize', -500, 'T', 'T')).toEqual({ end_min: 555 });
  });
});

describe('WeeklyGrid', () => {
  it('renders one block per event-day with accessible labels and confirmation markers', () => {
    render(<WeeklyGrid events={[lab, lec]} buildings={bmap} needsConfirm={{ 0: ['Only a start time was given'] }} />);
    expect(screen.getAllByTestId('grid-event')).toHaveLength(4);
    expect(screen.getByRole('button', { name: /Lab, Tue 9:00 AM to 12:00 PM at G\.G\. Brown Laboratory, needs confirmation/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Lab/ }).getAttribute('title')).toMatch(/From your text: “lab Tuesday 9 to noon in GG Brown”/);
  });
  it('moves an event 15 minutes with the keyboard and selects on Enter', () => {
    const onChange = vi.fn();
    const onSelect = vi.fn();
    render(<WeeklyGrid events={[lab]} buildings={bmap} onChange={onChange} onSelect={onSelect} />);
    const block = screen.getByRole('button', { name: /Lab/ });
    fireEvent.keyDown(block, { key: 'ArrowDown' });
    expect(onChange).toHaveBeenCalledWith(0, { start_min: 555, end_min: 735 });
    fireEvent.keyDown(block, { key: 'ArrowUp', shiftKey: true });
    expect(onChange).toHaveBeenLastCalledWith(0, { end_min: 705 });
    fireEvent.keyDown(block, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(0);
  });
  it('deletes with the Delete key and is inert when read-only', () => {
    const onDelete = vi.fn();
    const onChange = vi.fn();
    const { rerender } = render(<WeeklyGrid events={[lab]} buildings={bmap} onDelete={onDelete} onChange={onChange} />);
    fireEvent.keyDown(screen.getByRole('button', { name: /Lab/ }), { key: 'Delete' });
    expect(onDelete).toHaveBeenCalledWith(0);
    rerender(<WeeklyGrid events={[lab]} buildings={bmap} onDelete={onDelete} onChange={onChange} readOnly />);
    fireEvent.keyDown(screen.getByRole('button', { name: /Lab/ }), { key: 'ArrowDown' });
    expect(onChange).not.toHaveBeenCalled();
  });
});
