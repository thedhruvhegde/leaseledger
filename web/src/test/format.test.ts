import { clock, daysLabel, duration, frequency, hhmm, hours, ordinal, parseHhmm, per100, signed, signedUsd, snap, usd, usdRate } from '../lib/format';

describe('format', () => {
  it('formats money', () => {
    expect(usd(1234.4)).toBe('$1,234');
    expect(usd(-0.2)).toBe('$0');
    expect(usd(null)).toBe('—');
    expect(usdRate(9.4)).toBe('$9.40');
    expect(signedUsd(42.4)).toBe('+$42');
    expect(signedUsd(-18)).toBe('−$18');
    expect(signedUsd(0.3)).toBe('±$0');
  });
  it('formats durations and hours', () => {
    expect(duration(45)).toBe('45 min');
    expect(duration(135)).toBe('2 h 15 min');
    expect(duration(120)).toBe('2 h');
    expect(hours(412)).toBe('6.9 h');
    expect(signed(1.25, 'h', 1)).toBe('+1.3 h');
    expect(signed(-3, 'min')).toBe('−3 min');
  });
  it('formats clock times across midnight (service day)', () => {
    expect(clock(540)).toBe('9:00 AM');
    expect(clock(1500)).toBe('1:00 AM');
    expect(clock(720)).toBe('12:00 PM');
    expect(clock(1050, { compact: true })).toBe('5:30p');
    expect(hhmm(1500)).toBe('01:00');
    expect(parseHhmm('01:00')).toBe(1500);
    expect(parseHhmm('09:30')).toBe(570);
    expect(parseHhmm('25:00')).toBeNull();
  });
  it('labels days', () => {
    expect(daysLabel(['M', 'W', 'F'])).toBe('Mon, Wed, Fri');
    expect(daysLabel(['F', 'R', 'W', 'T', 'M'])).toBe('Weekdays');
    expect(daysLabel(['S', 'U'])).toBe('Weekends');
  });
  it('uses frequency formats', () => {
    expect(frequency(0.656, 2000)).toBe('1,312 of 2,000');
    expect(per100(0.656)).toBe(66);
    expect(per100(1.2)).toBe(100);
  });
  it('misc', () => {
    expect(snap(52)).toBe(45);
    expect(snap(53)).toBe(60);
    expect(ordinal(1)).toBe('1st');
    expect(ordinal(12)).toBe('12th');
    expect(ordinal(23)).toBe('23rd');
  });
});
