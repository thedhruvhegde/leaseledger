import { factLabel, factValue, ruleLabel } from '../lib/format';

describe('extracted listing facts read as words', () => {
  it('labels, values and rule ids', () => {
    expect(factLabel('fee:application_fee')).toBe('Application fee');
    expect(factValue('fee:application_fee', 75)).toBe('$75');
    expect(factValue('rent', 2550)).toBe('$2,550');
    expect(factValue('pets_allowed', true)).toBe('Yes');
    expect(factValue('lease_term_months', 12)).toBe('12 months');
    expect(ruleLabel('a2_application_fee_over_50')).toBe('Application fee over $50');
    expect(ruleLabel('Ann Arbor §8:532 bans pre-tenancy fees')).toBe('Ann Arbor §8:532 bans pre-tenancy fees');
  });
});
