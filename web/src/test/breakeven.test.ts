import { breakevenSide } from '../components/Breakeven';
import type { Breakeven } from '../types';

const be = (direction: string, value = 15.28) => ({ a: 'icc', b: 'ut', parameter: 'value_of_time', value, direction }) as Breakeven;
const A = 'ICC Escher House - double room (co-op)';
const B = 'University Towers - 2BR shared (up to 4 people)';

describe('breakevenSide', () => {
  it('reads the low-side winner from the engine text (A wins below => B wins above)', () => {
    const b = be(`${A} wins if value_of_time < $15.28/h; ${B} wins above it (you use $8.00/h)`);
    expect(breakevenSide(b, { a: A, b: B, vot: 8 })).toBe('above');
  });
  it('B named first => B wins below', () => {
    const b = be(`${B} wins if value_of_time < $15.28/h; ${A} wins above it (you use $20.00/h)`);
    expect(breakevenSide(b, { a: A, b: B, vot: 20 })).toBe('below');
  });
  it('without names, assumes A is ahead at your value so B wins on the far side', () => {
    expect(breakevenSide(be('X wins if value_of_time < $15.28/h; Y wins above it'), { vot: 8 })).toBe('above');
  });
});
