import { useApp } from '../store/app';
import { useDemoProfiles } from '../api/hooks';
import { EmptyState } from './ui/Misc';

/** Shown instead of results until the student has at least one event or a template. */
export function NoWeek() {
  const setScreen = useApp((s) => s.setScreen);
  const setProfile = useApp((s) => s.setProfile);
  const { data: demos = [] } = useDemoProfiles();
  return (
    <EmptyState title="Start with your week" action={
      <div className="flex flex-wrap justify-center gap-2">
        <button className="btn-primary" onClick={() => setScreen('week')}>Describe your week</button>
        {demos[0] && <button className="btn-outline" onClick={() => setProfile(demos[0].profile, 'load')}>Try “{demos[0].name}”</button>}
      </div>
    }>
      Homes are priced against your routine — add a class, job or study block (or pick a program template) and the ranking appears here.
    </EmptyState>
  );
}
