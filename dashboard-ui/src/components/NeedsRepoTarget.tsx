import {ChevronDown, Plus} from 'lucide-react';
import {ProjectRepo} from '../dashboardData';

export type NeedsRepoTargetProps = {
  targetRepos: ProjectRepo[];
  onTargetChange: (value: string) => void;
  message?: string;
  showPicker?: boolean;
};

export default function NeedsRepoTarget({
  targetRepos,
  onTargetChange,
  message = 'Pick a repo to run checks against.',
  showPicker = true,
}: NeedsRepoTargetProps) {
  return (
    <div className="needs-repo-target" role="note">
      <span className="needs-repo-target-text">{message}</span>
      {showPicker && (
        <label className="needs-repo-target-picker">
          <span className="sr-only">Pick a repo to target</span>
          <select
            name="needs-repo-target"
            aria-label="Pick a repo to run checks against"
            value=""
            onChange={(event) => {
              const value = event.target.value;
              if (value) onTargetChange(value);
            }}
          >
            <option value="" disabled>
              Choose repo…
            </option>
            {targetRepos.map((repo) => (
              <option key={repo.path} value={`repo:${repo.path}`}>
                {repo.name}
              </option>
            ))}
          </select>
          <ChevronDown size={14} aria-hidden="true" />
        </label>
      )}
      {showPicker && (
        <button
          type="button"
          className="needs-repo-target-add"
          onClick={() => onTargetChange('add-repo')}
        >
          <Plus size={14} /> Add repo
        </button>
      )}
    </div>
  );
}
