{{/*
Expand the name of the chart.
*/}}
{{- define "openstack-api-simulator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "openstack-api-simulator.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "openstack-api-simulator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "openstack-api-simulator.labels" -}}
helm.sh/chart: {{ include "openstack-api-simulator.chart" . }}
{{ include "openstack-api-simulator.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "openstack-api-simulator.selectorLabels" -}}
app.kubernetes.io/name: {{ include "openstack-api-simulator.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Service account name
*/}}
{{- define "openstack-api-simulator.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "openstack-api-simulator.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Image reference
*/}}
{{- define "openstack-api-simulator.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion }}
{{- printf "%s:%s" .Values.image.repository $tag }}
{{- end }}

{{/*
Secret name holding DATABASE_URL and TICKET_SIGNING_KEY
*/}}
{{- define "openstack-api-simulator.secretName" -}}
{{- if .Values.secret.existingSecret }}
{{- .Values.secret.existingSecret }}
{{- else }}
{{- include "openstack-api-simulator.fullname" . }}
{{- end }}
{{- end }}

{{/*
PostgreSQL hostname when bundled subchart is enabled
*/}}
{{- define "openstack-api-simulator.postgresqlHost" -}}
{{- printf "%s-postgresql" .Release.Name }}
{{- end }}

{{/*
Build DATABASE_URL when not supplied explicitly (bundled or external discrete fields).
*/}}
{{- define "openstack-api-simulator.databaseUrl" -}}
{{- if .Values.secret.databaseUrl }}
{{- .Values.secret.databaseUrl }}
{{- else if .Values.postgresql.enabled }}
{{- $user := .Values.postgresql.auth.username }}
{{- $pass := .Values.postgresql.auth.password }}
{{- $db := .Values.postgresql.auth.database }}
{{- $host := include "openstack-api-simulator.postgresqlHost" . }}
{{- printf "postgresql://%s:%s@%s:5432/%s" $user $pass $host $db }}
{{- else if .Values.externalDatabase.host }}
{{- $user := .Values.externalDatabase.user }}
{{- $pass := .Values.externalDatabase.password }}
{{- $db := .Values.externalDatabase.database }}
{{- $host := .Values.externalDatabase.host }}
{{- $port := int .Values.externalDatabase.port }}
{{- printf "postgresql://%s:%s@%s:%d/%s" $user $pass $host $port $db }}
{{- else }}
{{- fail "Set postgresql.enabled=true, or secret.databaseUrl / secret.existingSecret, or externalDatabase.host" }}
{{- end }}
{{- end }}

{{/*
cert-manager ClusterIssuer name used by Ingress
*/}}
{{- define "openstack-api-simulator.clusterIssuer" -}}
{{- if .Values.certManager.useStaging }}
{{- .Values.certManager.stagingIssuerName }}
{{- else }}
{{- .Values.certManager.issuerName }}
{{- end }}
{{- end }}
