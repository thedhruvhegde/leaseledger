import { signedUsd, surplusSentence } from '../screens/GroupScreen';

describe('Group Week worst-off surplus wording', () => {
  it('always shows the sign of the surplus', () => {
    expect(signedUsd(-328.4)).toBe('−$328');
    expect(signedUsd(41.6)).toBe('+$42');
    expect(signedUsd(0)).toBe('$0');
  });
  it('explains a negative surplus as cost above value and points to a better apartment', () => {
    const t = surplusSentence(-328, 'Roommate B', false, 'Six11');
    expect(t).toMatch(/costs Roommate B \$328\/mo more .* than the value they put on it/);
    expect(t).toMatch(/Consider Six11/);
  });
  it('says when even the best apartment leaves someone behind', () => {
    expect(surplusSentence(-50, 'Roommate A', true, null)).toMatch(/least bad/);
  });
  it('reads a positive surplus as everyone ahead', () => {
    expect(surplusSentence(120, 'Roommate C', true, null)).toMatch(/Everyone comes out ahead: even Roommate C/);
  });
});
