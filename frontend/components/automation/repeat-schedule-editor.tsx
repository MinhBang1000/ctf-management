"use client";

import type { RepeatKind, RepeatSchedule } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

interface Props {
  idPrefix: string;
  value: RepeatSchedule;
  onChange: (value: RepeatSchedule) => void;
}

// Apple-Reminders-style: pick a repeat cadence, then only the fields that
// cadence actually needs (day of week for weekly/biweekly, day of month
// for monthly, interval for custom) show up.
export function RepeatScheduleEditor({ idPrefix, value, onChange }: Props) {
  function set(patch: Partial<RepeatSchedule>) {
    onChange({ ...value, ...patch });
  }

  return (
    <div className="space-y-3">
      <label className="flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" checked={value.enabled} onChange={(e) => set({ enabled: e.target.checked })} />
        Enabled
      </label>

      {value.enabled && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor={`${idPrefix}-repeat`}>Repeat</Label>
            <Select
              id={`${idPrefix}-repeat`}
              value={value.repeat}
              onChange={(e) => set({ repeat: e.target.value as RepeatKind })}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="biweekly">Every 2 weeks</option>
              <option value="monthly">Monthly</option>
              <option value="custom">Custom interval</option>
            </Select>
          </div>

          <div>
            <Label htmlFor={`${idPrefix}-time`}>Time (UTC)</Label>
            <Input
              id={`${idPrefix}-time`}
              type="time"
              value={value.time_of_day.slice(0, 5)}
              onChange={(e) => set({ time_of_day: `${e.target.value}:00` })}
            />
          </div>

          {(value.repeat === "weekly" || value.repeat === "biweekly") && (
            <div>
              <Label htmlFor={`${idPrefix}-dow`}>Day of week</Label>
              <Select
                id={`${idPrefix}-dow`}
                value={value.day_of_week ?? 0}
                onChange={(e) => set({ day_of_week: Number(e.target.value) })}
              >
                {WEEKDAYS.map((d, i) => (
                  <option key={d} value={i}>
                    {d}
                  </option>
                ))}
              </Select>
            </div>
          )}

          {value.repeat === "monthly" && (
            <div>
              <Label htmlFor={`${idPrefix}-dom`}>Day of month</Label>
              <Input
                id={`${idPrefix}-dom`}
                type="number"
                min={1}
                max={31}
                value={value.day_of_month ?? 1}
                onChange={(e) => set({ day_of_month: Number(e.target.value) })}
              />
            </div>
          )}

          {value.repeat === "custom" && (
            <div>
              <Label htmlFor={`${idPrefix}-interval`}>Every N days</Label>
              <Input
                id={`${idPrefix}-interval`}
                type="number"
                min={1}
                max={365}
                value={value.interval_days ?? 1}
                onChange={(e) => set({ interval_days: Number(e.target.value) })}
              />
            </div>
          )}
        </div>
      )}

      {value.last_fired_at && (
        <p className="text-xs text-muted">Last fired: {new Date(value.last_fired_at).toLocaleString()}</p>
      )}
    </div>
  );
}
