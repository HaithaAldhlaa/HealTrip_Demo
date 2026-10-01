"use client";

import type { Provider } from "@/lib/api";

type Props = {
  provider: Provider;
  labels: {
    doctor: string;
    hospital: string;
    specialties: string;
    at: string;
    emergency: string;
    noEmergency: string;
    languages: string;
    address: string;
  };
};

/** Renders one verified provider record returned by the backend tool. */
export default function ProviderCard({ provider, labels }: Props) {
  return (
    <div className="provider-card">
      <div className="provider-name">{provider.name}</div>
      {provider.name_ar ? (
        <div className="provider-line" dir="rtl">
          {provider.name_ar}
        </div>
      ) : null}
      <div className="provider-line">
        {provider.type === "doctor" ? labels.doctor : labels.hospital} · {provider.city}
      </div>
      <div className="provider-line">
        {labels.specialties}:{" "}
        {provider.specialties.map((specialty) => (
          <span className="tag" key={specialty}>
            {specialty}
          </span>
        ))}
      </div>
      {provider.hospital ? (
        <div className="provider-line">
          {labels.at}: {provider.hospital}
          {provider.hospital_address ? ` — ${provider.hospital_address}` : ""}
        </div>
      ) : provider.hospital_address ? (
        <div className="provider-line">
          {labels.address}: {provider.hospital_address}
        </div>
      ) : null}
      {provider.emergency_available === true ? (
        <div className="provider-line">{labels.emergency}</div>
      ) : provider.emergency_available === false ? (
        <div className="provider-line">{labels.noEmergency}</div>
      ) : null}
      {provider.languages.length > 0 ? (
        <div className="provider-line">
          {labels.languages}: {provider.languages.join(" · ")}
        </div>
      ) : null}
    </div>
  );
}