import { Card, Typography, Space, Alert, Divider } from 'antd';
import {
  SafetyOutlined,
  FileProtectOutlined,
  MailOutlined,
  WarningOutlined,
} from '@ant-design/icons';

const { Title, Paragraph, Text, Link } = Typography;

export default function Legal() {
  return (
    <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: 900 }}>
      <Card>
        <Title level={2}>
          <SafetyOutlined /> LED Matrix Manager - Rechtliche Hinweise
        </Title>
        <Alert
          message="Wichtiger Hinweis"
          description="LED Matrix Manager ist ein Verwaltungs- und Steuerungstool für LED-Matrixgeräte. Die Nutzung erfolgt auf eigene Verantwortung des Benutzers."
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      </Card>

      <Card
        title={
          <>
            <FileProtectOutlined /> Impressum
          </>
        }
      >
        <Paragraph>
          <Text strong>Verantwortliche Person:</Text>
        </Paragraph>

        <Paragraph>
          Michael Kraemer
          <br />
        </Paragraph>

        <Divider />

        <Paragraph>
          <Text strong>Kontakt:</Text>
          <br />
          <MailOutlined /> E-Mail:{' '}
          <Link href="mailto:mkraemer.mk@gmail.com">mkraemer.mk@gmail.com</Link>
          <br />
        </Paragraph>
      </Card>

      <Card title="📜 Lizenz und Nutzungsbedingungen">
        <Paragraph>
          <Text strong>LED Matrix Manager</Text>
        </Paragraph>

        <Paragraph>
          Dieses Tool wird unter der <Text strong>MIT License</Text> bereitgestellt. Eine
          Zusammenfassung der Lizenzbestimmungen:
        </Paragraph>

        <ul>
          <li>✅ Kostenlos nutzbar für private, interne und wissenschaftliche Zwecke</li>
          <li>✅ Quellcode darf angesehen und modifiziert werden</li>
          <li>✅ Quellcode darf weitergegeben und verteilt werden</li>
          <li>
            ❌ <Text strong>Kommerzielle Nutzung nur mit ausdrücklicher Genehmigung</Text>
          </li>
          <li>❌ Keine Verantwortung für Schäden durch Nutzung</li>
        </ul>

        <Paragraph style={{ marginTop: 16 }}>
          <Text strong>Bedeutet konkret:</Text>
          <ul>
            <li>Du kannst LED Matrix Manager zur Verwaltung deiner Geräte verwenden</li>
            <li>Du kannst den Code studieren und für deine Bedürfnisse anpassen</li>
            <li>Du darfst das Tool nicht kommerziell verkaufen oder vermieten</li>
            <li>
              Du darfst das Tool nicht in ein kommerzielles Produkt einbauen (ohne Genehmigung)
            </li>
            <li>Du darfst das Tool nicht als Service anbieten (ohne Genehmigung)</li>
          </ul>
        </Paragraph>
      </Card>

      <Card title="🔒 Datenschutz">
        <Paragraph>
          <Text strong>Datenschutz bei LED Matrix Manager:</Text>
        </Paragraph>

        <Paragraph>Dieses Tool ist so konzipiert, dass es:</Paragraph>

        <ul>
          <li>✅ Keine Tracking-Tools enthält (kein Google Analytics, etc.)</li>
          <li>✅ Keine Cookies für Marketing oder Tracking setzt</li>
          <li>✅ Keine Daten an Dritte weitergibt</li>
          <li>✅ Nur lokal oder in deiner eigenen Installation Daten speichert</li>
          <li>✅ Keine Telemetrie oder Benutzeranalyse durchführt</li>
        </ul>

        <Paragraph style={{ marginTop: 16 }}>
          <Text strong>Datenverarbeitung:</Text>
        </Paragraph>

        <Paragraph>
          LED Matrix Manager verarbeitet nur folgende Daten, die du selbst eingibst:
        </Paragraph>

        <ul>
          <li>Szenen-Konfigurationen (Frames, Pixelfarben, Einstellungen)</li>
          <li>Geräte-Informationen (Namen, Adressen, Verbindungsdaten)</li>
          <li>Benutzer-Konten (wenn mit Authentifizierung betrieben)</li>
        </ul>

        <Paragraph>
          Diese Daten werden <Text strong>nicht</Text> übertragen, weitergegeben oder analysiert.
        </Paragraph>
      </Card>

      <Card title="⚠️ Haftungsausschluss (Disclaimer)">
        <Paragraph>
          <Text strong>1. Keine Gewährleistung</Text>
        </Paragraph>
        <Paragraph>
          LED Matrix Manager wird &quot;wie vorliegend&quot; (AS IS) ohne jegliche Gewährleistung
          bereitgestellt. Der Autor übernimmt keine Garantie für:
        </Paragraph>
        <ul>
          <li>Fehlerfreiheit des Codes oder der Funktionalität</li>
          <li>Eignung für einen bestimmten Zweck</li>
          <li>Unterbrechungsfreiheit oder ununterbrochene Verfügbarkeit</li>
          <li>Kompatibilität mit bestimmten Geräten oder Systemen</li>
        </ul>

        <Paragraph>
          <Text strong>2. Nutzung auf eigene Verantwortung</Text>
        </Paragraph>
        <Paragraph>
          <Text strong>
            Die Nutzung von LED Matrix Manager erfolgt vollständig auf deine eigene Verantwortung.
          </Text>
        </Paragraph>

        <Paragraph>Der Benutzer trägt allein die Verantwortung für:</Paragraph>
        <ul>
          <li>Ausfallzeiten oder Datenverluste</li>
          <li>Beschädigungen an LED-Geräten oder Hardware</li>
          <li>Falsch konfigurierte Einstellungen oder Parameter</li>
          <li>Kompatibilitätsprobleme mit seiner Hardware</li>
          <li>Sicherheitslücken oder Übernahmen durch Dritte</li>
        </ul>

        <Paragraph>
          <Text strong>3. Haftungsausschluss</Text>
        </Paragraph>
        <Paragraph>In keinem Fall ist der Autor haftbar für:</Paragraph>
        <ul>
          <li>Direkte oder indirekte Schäden</li>
          <li>Datenverluste oder Datenbeschädigungen</li>
          <li>Entgangene Gewinne oder Geschäftsunterbrechnungen</li>
          <li>Schäden an Geräten oder Hardware</li>
          <li>Alle sonstigen Schäden, die durch die Nutzung entstehen</li>
        </ul>

        <Alert
          message="Empfehlung vor Produktionsnutzung"
          description={
            <>
              <Text>
                Falls du LED Matrix Manager in einer produktiven oder kritischen Umgebung einsetzt:
              </Text>
              <ul style={{ marginBottom: 0, paddingLeft: 20, marginTop: 8 }}>
                <li>Erstelle regelmäßige Backups deiner Konfigurationen</li>
                <li>Teste alle Szenen und Einstellungen vor dem Produktiveinsatz</li>
                <li>Nutze geeignete Hardware-Schutzmaßnahmen</li>
                <li>Implementiere dein eigenes Monitoring und Fehlerbehandlung</li>
                <li>Halte dich über Updates auf dem Laufenden</li>
              </ul>
            </>
          }
          type="error"
          showIcon
          style={{ marginTop: 16 }}
        />

        <Paragraph style={{ marginTop: 16 }}>
          <Text strong>4. Verwendete Technologien</Text>
        </Paragraph>

        <Paragraph>
          <Text strong>Frontend:</Text>
        </Paragraph>
        <ul>
          <li>
            <Link href="https://reactjs.org" target="_blank">
              React
            </Link>{' '}
            - MIT License
          </li>
          <li>
            <Link href="https://vitejs.dev" target="_blank">
              Vite
            </Link>{' '}
            - MIT License
          </li>
          <li>
            <Link href="https://ant.design" target="_blank">
              Ant Design
            </Link>{' '}
            - MIT License
          </li>
        </ul>

        <Paragraph>
          <Text strong>Backend:</Text>
        </Paragraph>
        <ul>
          <li>
            <Link href="https://flask.palletsprojects.com" target="_blank">
              Flask
            </Link>{' '}
            - BSD-3-Clause License
          </li>
          <li>
            <Link href="https://www.sqlalchemy.org" target="_blank">
              SQLAlchemy
            </Link>{' '}
            - MIT License
          </li>
          <li>
            <Link href="https://gunicorn.org" target="_blank">
              Gunicorn
            </Link>{' '}
            - MIT License
          </li>
        </ul>
      </Card>

      <Card>
        <Paragraph style={{ textAlign: 'center', marginBottom: 0 }}>
          <Text type="secondary">
            Stand:{' '}
            {new Date().toLocaleDateString('de-DE', {
              year: 'numeric',
              month: 'long',
              day: 'numeric',
            })}
          </Text>
        </Paragraph>
      </Card>
    </Space>
  );
}
