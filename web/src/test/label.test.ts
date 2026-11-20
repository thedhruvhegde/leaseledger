import { compactLabel, fitLabel, labelCandidates, shortPlace } from '../lib/label';
import type { Building } from '../types';

const B = (id: string, name: string, aliases: string[]) => ({ id, name, aliases, campus: 'north', lat: 0, lon: 0 }) as unknown as Building;
const bbb = B('bbb', 'Bob and Betty Beyster Building', ['BBB', 'Beyster']);
const ccrb = B('ccrb', 'Central Campus Recreation Building', ['CCRB']);

describe('compactLabel', () => {
  it('keeps course code + room for narrow timeline blocks', () => {
    expect(compactLabel({ label: 'EECS 281 lecture in BBB' }, bbb)).toBe('EECS 281 · BBB');
    expect(compactLabel({ label: 'eecs281 discussion' }, bbb)).toBe('EECS 281 · BBB');
  });
  it('drops the place tail from free labels', () => {
    expect(compactLabel({ label: 'gym at CCRB' }, ccrb)).toBe('gym · CCRB');
    expect(compactLabel({ label: 'CCRB' }, ccrb)).toBe('CCRB');
  });
  it('picks the shortest single-word alias as the place tag', () => {
    expect(shortPlace(bbb)).toBe('BBB');
  });
});

describe('fitLabel', () => {
  const c = labelCandidates({ label: 'EECS 281 lecture in BBB' }, bbb);
  it('offers full, compact, code and number', () => {
    expect(c).toEqual(['EECS 281 lecture in BBB', 'EECS 281 · BBB', 'EECS 281', '281']);
  });
  it('picks the longest label that fits the block width', () => {
    expect(fitLabel(c, 300)).toBe('EECS 281 lecture in BBB');
    expect(fitLabel(c, 90)).toBe('EECS 281 · BBB');
    expect(fitLabel(c, 60)).toBe('EECS 281');
    expect(fitLabel(c, 26)).toBe('281');
    expect(fitLabel(c, 10)).toBe('');
  });
});
