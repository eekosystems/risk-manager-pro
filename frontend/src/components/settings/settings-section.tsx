interface SettingsSectionProps {
  title?: string;
  description?: string;
  children: React.ReactNode;
}

export function SettingsSection({ title, description, children }: SettingsSectionProps) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-6">
      {title && (
        <div className="mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
        </div>
      )}
      {children}
    </div>
  );
}
