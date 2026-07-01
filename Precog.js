window.addEventListener('dragover', function (e) { e.preventDefault(); });
window.addEventListener('drop', function (e) { e.preventDefault(); });

const { createApp, ref, computed } = Vue;

createApp({
  setup() {
    const dragOver = ref(false);
    const dragCounter = ref(0);
    const loadedFileNames = ref([]);
    const selectedPanel = ref('system');
    const keyword = ref('');
    const filterProvider = ref('All');
    const filterStatus = ref('All');
    const selectedOem = ref(null);
    const selectedDevice = ref(null);
    const deviceKeyword = ref('');
    const deviceOnlyProblem = ref(false);
    const deviceOnlyHighlighted = ref(false);
    const selectedProblemTab = ref('problem');
    const collapsedDeviceClasses = ref({});
    const jsonFilter = ref('');
    const regFilter = ref('');

    const dismDrivers = ref([]);
    const pnpDevices = ref([]);
    const pnpCsvDevices = ref([]);
    const problemDevices = ref([]);
    const pnpProblemDevices = ref([]);
    const pnpProblemCsvDevices = ref([]);
    const catalogMap = ref({});
    const sysInfo = ref({});
    const systemSummary = ref({});
    const collectionStatus = ref({});
    const runLogText = ref('');
    const rawWindowsVersionReg = ref('');
    const rawOSVersion = ref('');
    const showDecodedReg = ref(true);

    const rawDxDiagText = ref('');
    const rawPowerCfgA = ref('');
    const rawPowerCfgRequests = ref('');
    const rawPowerCfgLastWake = ref('');
    const rawPowerCfgWakeArmed = ref('');
    const rawSleepStudyText = ref('');
    const rawEnergyReportText = ref('');
    const displayAudioCameraRows = ref([]);
    const usbTypecRows = ref([]);
    const vendorRows = ref([]);
    const hardwareInventory = ref({});
    const installedAppsWin32 = ref([]);
    const installedAppsAppx = ref([]);
    const provisionedApps = ref([]);
    const startupApps = ref([]);
    const installedUpdates = ref([]);
    const servicesRows = ref([]);
    const scheduledTasksRows = ref([]);
    const showMicrosoftApps = ref(false);
    const rawDefaultAppsText = ref('');
    const rawPowerPlanText = ref('');
    const rawIPConfigText = ref('');
    const rawPnpInterfacesText = ref('');
    const rawScheduledTasksText = ref('');


    const statusOptions = ['All', 'Installed', 'No Device', 'Problem'];

    const hasData = computed(() => !!(dismDrivers.value.length || pnpDevices.value.length || pnpCsvDevices.value.length || Object.keys(systemSummary.value).length || Object.keys(sysInfo.value).length || Object.keys(hardwareInventory.value).length));

    function navClass(panel) {
      return ['px-4 py-2 rounded-xl border text-sm font-semibold', selectedPanel.value === panel ? 'bg-slate-900 text-white border-slate-900' : 'bg-white hover:bg-slate-50'].join(' ');
    }

    const providers = computed(() => [...new Set(dismDrivers.value.map(d => d.providerName).filter(Boolean))].sort((a, b) => a.localeCompare(b)));
    const winRegParsed = computed(() => parseWindowsVersionReg(rawWindowsVersionReg.value));
    const hiddenWinRegKeys = new Set(['DigitalProductId', 'DigitalProductId4']);

    const filteredSystemSummary = computed(() => {
      const q = jsonFilter.value.toLowerCase();
      return Object.fromEntries(Object.entries(systemSummary.value).filter(([k, v]) => !q || k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q)));
    });

    const filteredWinReg = computed(() => {
      const q = regFilter.value.toLowerCase();
      return Object.fromEntries(Object.entries(winRegParsed.value).filter(([k, v]) => !hiddenWinRegKeys.has(k) && (!q || k.toLowerCase().includes(q) || String(v).toLowerCase().includes(q))));
    });

    const systemHeadline = computed(() => {
      const src = Object.keys(systemSummary.value).length ? systemSummary.value : sysInfo.value;
      return {
        model: src.SystemModel || src.Model || src.ComputerModel || src.systemModel || '',
        sku: src.SystemSKU || src.SKU || src.systemSKU || '',
        bios: src.BIOSVersion || src.BIOS || src.biosVersion || '',
        os: src.OSName || src.OSVersion || src.osName || rawOSVersion.value.split(/\r?\n/).find(Boolean) || '',
        secureBoot: src.SecureBoot || src.SecureBootState || src.secureBoot || '',
        build: [winRegParsed.value.DisplayVersion || winRegParsed.value.ReleaseId, winRegParsed.value.CurrentBuild || src.OSBuild, winRegParsed.value.UBR].filter(Boolean).join(' / ')
      };
    });

    const secureBootClass = computed(() => {
      const v = (systemHeadline.value.secureBoot || '').toLowerCase();
      if (v.includes('on')) return 'text-emerald-600';
      if (v.includes('off')) return 'text-amber-600';
      return 'text-slate-700';
    });

    const problemDevicesCombined = computed(() => {
      const map = new Map();
      const realProblemRows = pnpProblemCsvDevices.value.filter(d => !isGhostProblemRecord(d));
      [...problemDevices.value, ...pnpProblemDevices.value, ...realProblemRows].forEach((d, idx) => {
        const baseId = (d.pnpId || d.instanceId || d.InstanceId || '').toLowerCase().trim();
        const name = (d.name || d.description || d.FriendlyName || '').toLowerCase().trim();
        const problem = (d.error || d.problem || d.Problem || d.ConfigManagerErrorCode || '').toLowerCase().trim();
        const key = baseId || [name, problem].filter(Boolean).join('|') || String(idx);
        if (!map.has(key)) map.set(key, d);
      });
      return [...map.values()];
    });

    const ghostDevices = computed(() => {
      const map = new Map();
      pnpProblemCsvDevices.value.filter(isGhostProblemRecord).forEach((d, idx) => {
        const baseId = (d.pnpId || d.instanceId || d.InstanceId || '').toLowerCase().trim();
        const key = baseId || `${d.FriendlyName || d.name || d.description || 'ghost'}-${idx}`;
        if (!map.has(key)) map.set(key, d);
      });
      return [...map.values()].sort((a, b) => (a.Class || '').localeCompare(b.Class || '') || (a.FriendlyName || '').localeCompare(b.FriendlyName || ''));
    });

    const summaryCards = computed(() => {
      let installed = 0, storeOnly = 0, problemDrivers = 0, nonWhql = 0;
      dismDrivers.value.forEach(d => {
        const st = checkOemStatus(d);
        if (st.isInstalled) installed++;
        else if (!st.hasDevice) storeOnly++;
        if (st.isProblem) problemDrivers++;
        if (isNonWhql(d)) nonWhql++;
      });
      return { totalDrivers: dismDrivers.value.length, installed, storeOnly, problem: problemDevicesCombined.value.length + nonWhql };
    });


    const collectionOkCount = computed(() => Object.values(collectionStatus.value).filter(v => String(v).toUpperCase() === 'OK').length);
    const collectionMissingCount = computed(() => Object.values(collectionStatus.value).filter(v => String(v).toUpperCase() !== 'OK').length);
    const systemHealthLoadedCount = computed(() => [rawPowerCfgA.value, rawPowerCfgRequests.value, rawPowerCfgLastWake.value, rawPowerCfgWakeArmed.value, rawSleepStudyText.value].filter(Boolean).length);
    const systemInfoGeneratedTime = computed(() => {
      const hw = hardwareInventory.value || {};
      return hw.GeneratedAt || systemSummary.value.Timestamp || systemSummary.value.TimeStamp || 'N/A';
    });

    function firstConfigValue(sectionTitle) {
      const section = platformConfigurationSections.value.find(s => s.title === sectionTitle);
      if (!section || !section.rows || !section.rows.length) return 'N/A';
      const row = section.rows[0];
      return [row.name, row.detail].filter(Boolean).join(' | ') || 'N/A';
    }

    const hardwareSummaryRows = computed(() => [
      { label: 'CPU', value: firstConfigValue('CPU') },
      { label: 'Memory', value: firstConfigValue('Memory') || (systemSummary.value.TotalPhysicalMemoryGB ? `${systemSummary.value.TotalPhysicalMemoryGB} GB` : 'N/A') },
      { label: 'Storage', value: firstConfigValue('Storage') },
      { label: 'Graphics', value: firstConfigValue('Graphics') },
      { label: 'Display', value: firstConfigValue('Display / Panel') },
      { label: 'Battery', value: firstConfigValue('Battery') }
    ]);

    const finalFilteredDrivers = computed(() => {
      const q = keyword.value.toLowerCase();
      return dismDrivers.value.filter(d => {
        const providerMatch = filterProvider.value === 'All' || d.providerName === filterProvider.value;
        const st = checkOemStatus(d);
        const signer = getSignerSummary(d).toLowerCase();
        const matched = getMatchedPnpDevices(d);
        const searchText = [d.publishedName, d.originalName, d.providerName, d.version, signer, ...matched.map(m => [m.description, m.instanceId, m.deviceClass, (m.hwids || []).join(' ')].join(' '))].join(' ').toLowerCase();
        const keywordMatch = !q || searchText.includes(q);
        let statusMatch = true;
        if (filterStatus.value === 'Installed') statusMatch = st.isInstalled;
        if (filterStatus.value === 'No Device') statusMatch = !st.hasDevice;
        if (filterStatus.value === 'Problem') statusMatch = st.isProblem || isNonWhql(d);
        return providerMatch && keywordMatch && statusMatch;
      }).sort((a, b) => {
        const na = parseInt((a.publishedName || '').replace(/\D/g, ''), 10);
        const nb = parseInt((b.publishedName || '').replace(/\D/g, ''), 10);
        if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
        return (a.publishedName || '').localeCompare(b.publishedName || '');
      });
    });

    const matchedPnpDevices = computed(() => selectedOem.value ? getMatchedPnpDevices(selectedOem.value) : []);

    const fullDeviceList = computed(() => {
      const map = new Map();
      pnpCsvDevices.value.forEach(r => {
        const id = r.InstanceId || r.instanceId || '';
        if (!id) return;
        const ghost = isGhostProblemRecord(r);
        map.set(id.toLowerCase(), {
          name: r.FriendlyName || r.Name || 'Unknown Device',
          instanceId: id,
          className: r.Class || 'Unknown',
          status: r.Status || '',
          problem: normalizeProblem(r.Problem || r.ConfigManagerErrorCode || ''),
          isProblem: !ghost && isProblemStatus(r.Status, r.Problem, r.ConfigManagerErrorCode),
          isGhost: ghost,
          hwids: [],
          matchingDrivers: [],
          activeDriver: '',
          activeDriverStatus: '',
          signer: '',
          version: ''
        });
      });

      pnpProblemCsvDevices.value.filter(isGhostProblemRecord).forEach(r => {
        const id = r.InstanceId || r.instanceId || '';
        if (!id) return;
        const old = map.get(id.toLowerCase()) || {};
        map.set(id.toLowerCase(), {
          ...old,
          name: old.name || r.FriendlyName || r.Name || 'Unknown Device',
          instanceId: old.instanceId || id,
          className: old.className || r.Class || 'Ghost Device',
          status: old.status || r.Status || 'Unknown',
          problem: old.problem || r.Problem || r.ConfigManagerErrorCode || 'CM_PROB_PHANTOM',
          isProblem: old.isProblem || false,
          isGhost: true,
          hwids: old.hwids || [],
          matchingDrivers: old.matchingDrivers || [],
          activeDriver: old.activeDriver || '',
          activeDriverStatus: old.activeDriverStatus || '',
          signer: old.signer || '',
          version: old.version || ''
        });
      });
      pnpDevices.value.forEach(dev => {
        const id = dev.instanceId || '';
        if (!id) return;
        const active = getActiveMatchingDriver(dev);
        const problem = getProblemData(id);
        const base = map.get(id.toLowerCase()) || {};
        map.set(id.toLowerCase(), {
          name: dev.description || base.name || 'Unknown Device',
          instanceId: id,
          className: dev.deviceClass || base.className || 'Unknown',
          status: base.status || '',
          problem: problem ? (problem.error || problem.problem || problem.Problem || problem.ConfigManagerErrorCode || '') : (base.problem || ''),
          isProblem: !!problem || !!base.isProblem,
          isGhost: !!base.isGhost,
          hwids: dev.hwids || base.hwids || [],
          matchingDrivers: dev.matchingDrivers || [],
          activeDriver: active ? active.name : (base.activeDriver || ''),
          activeDriverStatus: active ? active.status : (base.activeDriverStatus || ''),
          signer: active ? active.signer : (base.signer || ''),
          version: active ? active.ver : (base.version || '')
        });
      });
      return [...map.values()].sort((a, b) => (a.className || '').localeCompare(b.className || '') || (a.name || '').localeCompare(b.name || ''));
    });

    const filteredDeviceGroups = computed(() => {
      const q = deviceKeyword.value.toLowerCase();
      const groups = new Map();
      fullDeviceList.value.forEach(dev => {
        if (deviceOnlyProblem.value && !dev.isProblem) return;
        if (deviceOnlyHighlighted.value && !isHighlightedDevice(dev)) return;
        const text = [dev.name, dev.instanceId, dev.className, dev.status, dev.problem, dev.activeDriver, dev.signer, (dev.hwids || []).join(' ')].join(' ').toLowerCase();
        if (q && !text.includes(q)) return;
        const cls = dev.className || 'Unknown';
        if (!groups.has(cls)) groups.set(cls, []);
        groups.get(cls).push(dev);
      });
      return [...groups.entries()].map(([className, devices]) => ({ className, devices })).sort((a, b) => a.className.localeCompare(b.className));
    });

    const platformHealthCards = computed(() => {
      const requestsText = rawPowerCfgRequests.value.trim();
      const requestsClear = requestsText && !/\b(?!DISPLAY|SYSTEM|AWAYMODE|EXECUTION|PERFBOOST|ACTIVELOCKSCREEN|None)\S+:/i.test(requestsText) && !/\[[^\]]+\]/.test(requestsText);
      return [
        { title: 'PowerCfg /a', status: rawPowerCfgA.value ? 'Loaded' : 'Missing', detail: rawPowerCfgA.value ? firstMeaningfulLine(rawPowerCfgA.value) : 'Not loaded' },
        { title: 'Power Requests', status: rawPowerCfgRequests.value ? (requestsClear ? 'OK' : 'Loaded') : 'Missing', detail: rawPowerCfgRequests.value ? (requestsClear ? 'No active requests detected' : 'Available for review') : 'Not loaded' },
        { title: 'Last Wake', status: rawPowerCfgLastWake.value ? 'Loaded' : 'Missing', detail: rawPowerCfgLastWake.value ? firstMeaningfulLine(rawPowerCfgLastWake.value) : 'Not loaded' },
        { title: 'Wake Armed', status: rawPowerCfgWakeArmed.value ? 'Loaded' : 'Missing', detail: rawPowerCfgWakeArmed.value ? firstMeaningfulLine(rawPowerCfgWakeArmed.value) : 'Not loaded' },
        { title: 'DxDiag', status: rawDxDiagText.value ? 'Loaded' : 'Missing', detail: rawDxDiagText.value ? getDxDiagHeadline(rawDxDiagText.value) : 'Not loaded' },
        { title: 'SleepStudy', status: rawSleepStudyText.value ? 'Loaded' : 'Missing', detail: rawSleepStudyText.value ? 'Modern Standby report loaded' : 'Not loaded' },
        { title: 'Energy Report', status: rawEnergyReportText.value ? 'Loaded' : 'Missing', detail: rawEnergyReportText.value ? 'Power efficiency report loaded' : 'Not loaded' },
        { title: 'Vendor Devices', status: vendorRows.value.length ? 'Loaded' : 'Missing', detail: vendorRows.value.length ? `${vendorRows.value.length} vendor-related rows` : 'Not loaded' }
      ];
    });

    function asArray(value) {
      if (!value) return [];
      return Array.isArray(value) ? value : [value];
    }

    function cleanText(value) {
      if (value === null || value === undefined || value === '') return '';
      return String(value).trim();
    }

    function joinDetails(values) {
      return values.map(cleanText).filter(Boolean).join(' | ');
    }

    function bytesToGB(value) {
      const n = Number(value);
      if (!Number.isFinite(n) || n <= 0) return '';
      return `${(n / 1024 / 1024 / 1024).toFixed(n > 100 * 1024 * 1024 * 1024 ? 0 : 1)} GB`;
    }

    function normalizeAppKey(value) {
      return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
    }

    function appDisplayName(app) {
      return app.DisplayName || app.Name || app.DisplayName || app.PackageFullName || app.PackageName || app.PSChildName || 'Unknown App';
    }

    function appPublisher(app) {
      return app.Publisher || app.PublisherDisplayName || '';
    }

    function isMicrosoftApp(app) {
      const name = appDisplayName(app).toLowerCase();
      const publisher = appPublisher(app).toLowerCase();
      const packageName = String(app.PackageName || app.PackageFullName || app.PackageFamilyName || '').toLowerCase();
      return publisher.includes('microsoft') ||
             publisher.includes('windows') ||
             packageName.includes('microsoft') ||
             name.startsWith('microsoft ') ||
             name.startsWith('windows ') ||
             name.includes('microsoft.') ||
             name.includes('windows.');
    }

    function appVersion(app) {
      return app.DisplayVersion || app.Version || '';
    }

    const combinedInstalledApps = computed(() => {
      const map = new Map();

      function addApp(row, source) {
        const name = appDisplayName(row);
        const version = appVersion(row);
        const publisher = appPublisher(row);
        const family = row.PackageFamilyName || row.PackageName || row.PackageFullName || row.PSChildName || '';
        const key = normalizeAppKey(name || family);
        if (!key) return;

        const current = map.get(key);
        const item = {
          name,
          version,
          publisher,
          source,
          packageName: row.PackageFullName || row.PackageName || row.PackageFamilyName || '',
          installLocation: row.InstallLocation || '',
          raw: row,
          isMicrosoft: isMicrosoftApp(row)
        };

        if (!current) {
          map.set(key, item);
        } else {
          const sources = new Set(String(current.source).split(' + ').concat(source));
          current.source = [...sources].filter(Boolean).join(' + ');
          current.version = current.version || version;
          current.publisher = current.publisher || publisher;
          current.packageName = current.packageName || item.packageName;
          current.installLocation = current.installLocation || item.installLocation;
          current.isMicrosoft = current.isMicrosoft || item.isMicrosoft;
        }
      }

      installedAppsWin32.value.forEach(r => addApp(r, 'Win32'));
      installedAppsAppx.value.forEach(r => addApp(r, 'Appx'));
      provisionedApps.value.forEach(r => addApp(r, 'Provisioned'));

      return [...map.values()]
        .filter(app => showMicrosoftApps.value ? app.isMicrosoft : !app.isMicrosoft)
        .sort((a, b) => a.name.localeCompare(b.name));
    });

    const filteredStartupApps = computed(() => {
      return startupApps.value
        .map(r => ({ ...r, isMicrosoft: isMicrosoftApp({ DisplayName: r.Name, Publisher: r.Command }) }))
        .filter(app => showMicrosoftApps.value ? app.isMicrosoft : !app.isMicrosoft)
        .sort((a, b) => String(a.Name || '').localeCompare(String(b.Name || '')));
    });

    const operationsLogCards = computed(() => [
      { title: 'Installed Updates', count: installedUpdates.value.length, kind: 'table' },
      { title: 'Services', count: servicesRows.value.length, kind: 'table' },
      { title: 'Startup Apps', count: startupApps.value.length, kind: 'table' },
      { title: 'Scheduled Tasks', count: scheduledTasksRows.value.length, kind: 'table' },
      { title: 'Power Plan', count: rawPowerPlanText.value ? rawPowerPlanText.value.split(/\r?\n/).filter(Boolean).length : 0, kind: 'text' },
      { title: 'IPConfig', count: rawIPConfigText.value ? rawIPConfigText.value.split(/\r?\n/).filter(Boolean).length : 0, kind: 'text' },
      { title: 'PnP Interfaces', count: rawPnpInterfacesText.value ? rawPnpInterfacesText.value.split(/\r?\n/).filter(Boolean).length : 0, kind: 'text' },
      { title: 'Default Apps', count: rawDefaultAppsText.value ? rawDefaultAppsText.value.split(/\r?\n/).filter(Boolean).length : 0, kind: 'text' }
    ]);

    function makeConfigRow(name, details = [], meta = []) {
      return {
        name: cleanText(name) || 'Unknown',
        detail: joinDetails(details),
        meta: joinDetails(meta)
      };
    }

    const platformConfigurationSections = computed(() => {
      const hw = hardwareInventory.value || {};
      const sections = [];

      const cpuRows = asArray(hw.CPU).map(cpu => makeConfigRow(
        cpu.Name,
        [cpu.NumberOfCores && cpu.NumberOfLogicalProcessors ? `${cpu.NumberOfCores}C / ${cpu.NumberOfLogicalProcessors}T` : (cpu.Cores && cpu.Threads ? `${cpu.Cores}C / ${cpu.Threads}T` : ''), cpu.MaxClockSpeed ? `${cpu.MaxClockSpeed} MHz` : (cpu.MaxClockMHz ? `${cpu.MaxClockMHz} MHz` : ''), cpu.Manufacturer],
        [cpu.SocketDesignation || cpu.Socket]
      ));
      sections.push({ title: 'CPU', badge: cpuRows.length ? `${cpuRows.length}` : '0', rows: cpuRows });

      const mem = hw.Memory || {};
      const memoryRows = asArray(mem.Modules).map(m => makeConfigRow(
        [m.Manufacturer, m.PartNumber].filter(Boolean).join(' ') || m.Slot || m.Bank,
        [m.CapacityGB ? `${m.CapacityGB} GB` : bytesToGB(m.Capacity), m.ConfiguredClockSpeedMHz ? `${m.ConfiguredClockSpeedMHz} MHz` : (m.ConfiguredClockSpeed ? `${m.ConfiguredClockSpeed} MHz` : (m.SpeedMHz ? `${m.SpeedMHz} MHz` : (m.Speed ? `${m.Speed} MHz` : ''))), m.Slot || m.Bank],
        [m.SerialNumber]
      ));
      sections.push({ title: 'Memory', badge: mem.TotalGB ? `${mem.TotalGB} GB` : `${memoryRows.length}`, rows: memoryRows });

      const storage = hw.Storage || {};
      const storageRows = asArray(storage.PhysicalDisks).map(d => makeConfigRow(
        d.FriendlyName || d.Model,
        [d.SizeGB ? `${d.SizeGB} GB` : bytesToGB(d.Size), d.BusType || d.InterfaceType, d.MediaType, d.HealthStatus],
        [d.SerialNumber]
      ));
      sections.push({ title: 'Storage', badge: storageRows.length ? `${storageRows.length}` : '0', rows: storageRows });

      const display = hw.Display || {};
      const monitorRows = asArray(display.Monitors).map(m => makeConfigRow(
        m.DisplayName || m.UserFriendlyName || m.Model || [m.Manufacturer, m.PanelCode || m.ProductCode || m.ManufacturerCode].filter(Boolean).join(' ') || 'Monitor',
        [m.Active === true ? 'Active' : (m.Active === false ? 'Inactive' : ''), m.Manufacturer || m.ManufacturerCode, m.Model || m.PanelCode || m.ProductCode],
        [m.InstanceName]
      ));
      sections.push({ title: 'Display / Panel', badge: monitorRows.length ? `${monitorRows.length}` : '0', rows: monitorRows });

      const gpuRows = asArray(hw.Graphics).map(g => makeConfigRow(
        g.Name,
        [g.DriverVersion, g.VideoProcessor, g.AdapterRAMGB ? `${g.AdapterRAMGB} GB VRAM` : '', g.CurrentHorizontalResolution && g.CurrentVerticalResolution ? `${g.CurrentHorizontalResolution}x${g.CurrentVerticalResolution}` : ''],
        [g.PNPDeviceID]
      ));
      sections.push({ title: 'Graphics', badge: gpuRows.length ? `${gpuRows.length}` : '0', rows: gpuRows });

      const network = hw.Network || {};
      const networkRows = asArray(network.Adapters).map(n => makeConfigRow(
        n.DisplayName || n.InterfaceDescription || n.NetConnectionID || n.Name,
        [n.Type, n.Status, n.LinkSpeed, n.Manufacturer, n.AdapterType, n.NetEnabled === true ? 'Enabled' : (n.NetEnabled === false ? 'Disabled' : '')],
        [n.MacAddress || n.MACAddress, n.InterfaceGuid, n.PNPDeviceID]
      ));
      sections.push({ title: 'Network', badge: networkRows.length ? `${networkRows.length}` : '0', rows: networkRows });

      const bluetoothRows = asArray(network.Bluetooth).map(b => makeConfigRow(
        b.FriendlyName,
        [b.Status, b.Problem],
        [b.InstanceId]
      ));
      sections.push({ title: 'Bluetooth', badge: bluetoothRows.length ? `${bluetoothRows.length}` : '0', rows: bluetoothRows });

      const audioRows = asArray(hw.Audio).map(a => makeConfigRow(
        a.FriendlyName,
        [a.Status, a.Problem],
        [a.InstanceId]
      ));
      sections.push({ title: 'Audio', badge: audioRows.length ? `${audioRows.length}` : '0', rows: audioRows });

      const cameraRows = asArray(hw.Camera).map(c => makeConfigRow(
        c.FriendlyName,
        [c.Class, c.Status, c.Problem],
        [c.InstanceId]
      ));
      sections.push({ title: 'Camera', badge: cameraRows.length ? `${cameraRows.length}` : '0', rows: cameraRows });

      const batteryRows = asArray(hw.Battery).map(b => makeConfigRow(
        b.Name || b.DeviceID,
        [b.Manufacturer, b.EstimatedChargeRemaining !== null && b.EstimatedChargeRemaining !== undefined ? `${b.EstimatedChargeRemaining}%` : '', b.BatteryStatus ? `Status ${b.BatteryStatus}` : ''],
        [b.DeviceID]
      ));
      sections.push({ title: 'Battery', badge: batteryRows.length ? `${batteryRows.length}` : '0', rows: batteryRows });

      const input = hw.Input || {};
      const inputRows = asArray(input.HID).slice(0, 50).map(i => makeConfigRow(
        i.FriendlyName,
        [i.Class, i.Status, i.Problem],
        [i.InstanceId]
      ));
      sections.push({ title: 'Input / HID', badge: inputRows.length ? `${inputRows.length}` : '0', rows: inputRows });

      const usbRows = asArray(hw.USB).slice(0, 80).map(u => makeConfigRow(
        u.FriendlyName,
        [u.Class, u.Status, u.Problem],
        [u.InstanceId]
      ));
      sections.push({ title: 'USB', badge: usbRows.length ? `${usbRows.length}` : '0', rows: usbRows });

      const tpm = asArray(hw.Security && hw.Security.TPM)[0] || asArray(hw.TPM)[0];
      const securityRows = tpm ? [makeConfigRow('TPM', [tpm.TpmPresent ? 'Present' : 'Not present', tpm.TpmReady ? 'Ready' : 'Not ready', tpm.ManufacturerIdTxt, tpm.SpecVersion], [tpm.ManufacturerVersion])] : [];
      sections.push({ title: 'Security', badge: securityRows.length ? `${securityRows.length}` : '0', rows: securityRows });

      return sections;
    });

    const platformConfigurationHeadline = computed(() => {
      const hw = hardwareInventory.value || {};
      const system = hw.System || {};
      return {
        model: [system.Manufacturer, system.Model].filter(Boolean).join(' ') || system.SystemSKU || 'N/A',
        sku: system.SystemSKU || 'N/A',
        bios: system.BIOSVersion || 'N/A',
        generatedAt: hw.Timestamp || hw.GeneratedAt || 'N/A'
      };
    });

    function resetTool() { location.reload(); }
    function onDragEnter(e) { if (e && e.dataTransfer && [...e.dataTransfer.types].includes('Files')) { dragCounter.value += 1; dragOver.value = true; } }
    function onDragOver(e) { if (e && e.dataTransfer) e.dataTransfer.dropEffect = 'copy'; dragOver.value = true; }
    function onDragLeave() { dragCounter.value -= 1; if (dragCounter.value <= 0) { dragCounter.value = 0; dragOver.value = false; } }
    function handleBatchUpload(e) { const files = Array.from((e.target && e.target.files) || []); if (files.length) processFiles(files); }
    function openFolderPicker() {
      const input = document.getElementById('folderInput');
      if (input) input.click();
    }
    function handleDrop(e) { dragCounter.value = 0; dragOver.value = false; const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []); if (files.length) processFiles(files); }

    function processFiles(files) {
      loadedFileNames.value = files.map(f => f.webkitRelativePath || f.name).sort((a, b) => a.localeCompare(b));
      selectedPanel.value = 'system';
      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = evt => {
          const name = file.name.toLowerCase();
          const text = evt.target.result;
          try {
            if (name.includes('_dism_driverinfo')) parseDism(text);
            else if (name.includes('_pnpdeviceinfo.csv')) pnpCsvDevices.value = parseCsv(text);
            else if (name.includes('_pnpdeviceinfo')) parsePnp(text);
            else if (name.includes('_pnpproblemdevices.csv')) pnpProblemCsvDevices.value = parseCsv(text);
            else if (name.includes('_pnpproblemdevices')) parsePnpProblem(text);
            else if (name.includes('_sysinfo')) parseSys(text);
            else if (name.includes('_catalogmap')) parseCatalog(text);
            else if (name.includes('_collectionstatus')) parseCollectionStatus(text);
            else if (name.includes('_systemsummary.json')) parseSystemSummary(text);
            else if (name.includes('_runlog')) runLogText.value = text;
            else if (name.includes('_windowsversionreg')) rawWindowsVersionReg.value = text;
            else if (name.includes('_osversion')) rawOSVersion.value = text;
            else if (name.includes('_dxdiag')) rawDxDiagText.value = text;
            else if (name.includes('_powercfg_a')) rawPowerCfgA.value = text;
            else if (name.includes('_powercfg_requests')) rawPowerCfgRequests.value = text;
            else if (name.includes('_powercfg_lastwake')) rawPowerCfgLastWake.value = text;
            else if (name.includes('_powercfg_wakearmed')) rawPowerCfgWakeArmed.value = text;
            else if (name.includes('_sleepstudy')) rawSleepStudyText.value = text;
            else if (name.includes('_energyreport')) rawEnergyReportText.value = text;
            else if (name.includes('_display_audio_camera_system')) displayAudioCameraRows.value = parseCsv(text);
            else if (name.includes('_usb_typec_ucsi')) usbTypecRows.value = parseCsv(text);
            else if (name.includes('_vendor_related_devices')) vendorRows.value = parseCsv(text);
            else if (name.includes('_hardwareinventory.json')) parseHardwareInventory(text);
            else if (name.includes('_installedapps_win32')) installedAppsWin32.value = parseCsv(text);
            else if (name.includes('_installedapps_appx')) installedAppsAppx.value = parseCsv(text);
            else if (name.includes('_provisionedapps')) provisionedApps.value = parseCsv(text);
            else if (name.includes('_startupapps')) startupApps.value = parseCsv(text);
            else if (name.includes('_installedupdates')) installedUpdates.value = parseCsv(text);
            else if (name.includes('_services')) servicesRows.value = parseCsv(text);
            else if (name.includes('_scheduledtasks.csv')) scheduledTasksRows.value = parseCsv(text);
            else if (name.includes('_scheduledtasks.txt')) rawScheduledTasksText.value = text;
            else if (name.includes('_powerplan')) rawPowerPlanText.value = text;
            else if (name.includes('_ipconfig')) rawIPConfigText.value = text;
            else if (name.includes('_pnpinterfaces')) rawPnpInterfacesText.value = text;
            else if (name.includes('_defaultappassociations')) rawDefaultAppsText.value = text;
          } catch (err) { console.error('Parse error in', file.name, err); }
        };
        reader.readAsText(file);
      });
    }

    function parseDism(text) {
      const lines = text.split(/\r?\n/), res = [];
      let started = false;
      for (const line of lines) {
        if (line.includes('Published Name')) { started = true; continue; }
        if (!started || !line.trim() || line.includes('---')) continue;
        const cols = line.split('|').map(c => c.trim());
        if (cols.length >= 7 && /^oem\d+\.inf$/i.test(cols[0])) res.push({ publishedName: cols[0].toLowerCase(), originalName: cols[1], providerName: cols[4], className: cols[3], version: cols[6], date: cols[5] });
      }
      dismDrivers.value = res;
    }

    function parsePnp(text) {
      const blocks = text.split(/Instance ID:\s+/), res = [];
      blocks.forEach(block => {
        if (!block.trim() || block.includes('Microsoft PnP Utility')) return;
        const lines = block.split(/\r?\n/);
        const dev = { instanceId: lines[0].trim(), description: '', deviceClass: '', hwids: [], matchingDrivers: [] };
        lines.forEach(line => {
          if (line.startsWith('Device Description:')) dev.description = line.split(/:(.+)/)[1]?.trim() || '';
          if (line.startsWith('Class Name:')) dev.deviceClass = line.split(/:(.+)/)[1]?.trim() || '';
        });
        const hwMatch = block.match(/Hardware IDs:([\s\S]*?)(?=Compatible IDs:|Matching Drivers:|$)/);
        if (hwMatch) dev.hwids = hwMatch[1].split(/\r?\n/).map(s => s.trim()).filter(Boolean);
        const matchPart = block.split('Matching Drivers:')[1];
        if (matchPart) {
          const driverBlocks = matchPart.split(/^\s+Driver Name:/m);
          driverBlocks.forEach(db => {
            if (!db.trim()) return;
            const dl = db.split(/\r?\n/);
            const info = { name: dl[0].trim().toLowerCase(), status: '', ver: '', date: '', signer: '' };
            dl.forEach(line => {
              if (line.includes('Driver Status:')) info.status = line.split(/:(.+)/)[1]?.trim() || '';
              if (line.includes('Driver Version:')) { const part = line.split(/:(.+)/)[1]?.trim() || ''; const pieces = part.split(/\s+/); info.date = pieces[0] || ''; info.ver = pieces.slice(1).join(' '); }
              if (line.includes('Signer Name:')) info.signer = line.split(/:(.+)/)[1]?.trim() || '';
            });
            dev.matchingDrivers.push(info);
          });
        }
        res.push(dev);
      });
      pnpDevices.value = res;
    }

    function parseSys(text) {
      const info = {}, pDevs = [];
      let section = '';
      text.split(/\r?\n/).forEach(line => {
        if (line.startsWith('[') && line.endsWith(']')) { section = line.trim(); return; }
        const parts = line.split('\t').map(s => s.trim());
        if (section === '[System Summary]' && parts.length >= 2) {
          if (parts[0] === 'OS Name') info.OSName = parts[1];
          if (parts[0] === 'System Model') info.SystemModel = parts[1];
          if (parts[0] === 'System SKU') info.SystemSKU = parts[1];
          if (parts[0] === 'BIOS Version/Date') info.BIOSVersion = parts[1];
          if (parts[0] === 'Total Physical Memory') info.TotalRAM = parts[1];
          if (parts[0] === 'Secure Boot State') info.SecureBoot = parts[1];
        }
        if (section === '[Problem Devices]' && parts.length >= 3 && parts[1] !== 'PNP Device ID' && parts[0] !== 'Device') pDevs.push({ name: parts[0], pnpId: parts[1], error: 'Error Code: ' + parts[2] });
      });
      sysInfo.value = info;
      problemDevices.value = pDevs;
    }

    function parseCatalog(text) {
      const rows = parseCsv(text), map = {};
      rows.forEach(r => {
        const key = (r.Driver || r.PublishedName || '').toLowerCase();
        const val = r.OriginalFileName || r.CatalogFile || '';
        if (key) map[key] = val;
      });
      catalogMap.value = map;
    }

    function parsePnpProblem(text) {
      const blocks = text.split(/Instance ID:\s+/), res = [];
      blocks.forEach(block => {
        if (!block.trim() || block.includes('Microsoft PnP Utility') || block.includes('No devices were found')) return;
        const lines = block.split(/\r?\n/);
        const item = { instanceId: lines[0].trim(), description: '', problem: '' };
        lines.forEach(line => {
          if (line.startsWith('Device Description:')) item.description = line.split(/:(.+)/)[1]?.trim() || '';
          if (line.startsWith('Problem Code:')) item.problem = 'Problem Code: ' + (line.split(/:(.+)/)[1]?.trim() || '');
          if (line.startsWith('Problem:')) item.problem = 'Problem: ' + (line.split(/:(.+)/)[1]?.trim() || '');
        });
        if (item.instanceId || item.description || item.problem) res.push(item);
      });
      pnpProblemDevices.value = res;
    }

    function parseCollectionStatus(text) {
      const map = {};
      text.split(/\r?\n/).forEach(line => {
        if (!line.includes('=')) return;
        const idx = line.indexOf('='), k = line.slice(0, idx).trim(), v = line.slice(idx + 1).trim();
        if (k && !['ComputerName', 'Timestamp', 'OutputFolder', 'KeepOutputFolderAfterZip'].includes(k)) map[k] = v;
      });
      collectionStatus.value = map;
    }

    function parseSystemSummary(text) { try { systemSummary.value = JSON.parse(text); } catch { systemSummary.value = {}; } }
    function parseHardwareInventory(text) { try { hardwareInventory.value = JSON.parse(text); } catch { hardwareInventory.value = {}; } }
    function parseWindowsVersionReg(text) { const obj = {}; text.split(/\r?\n/).forEach(line => { const m = line.match(/^\s*(\w+)\s+REG_\w+\s+(.+)$/); if (m) obj[m[1]] = m[2].trim(); }); return obj; }

    function parseCsv(text) {
      const rows = [];
      const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).filter(l => l.trim());
      if (!lines.length) return rows;
      const headers = splitCsvLine(lines[0]).map(h => h.trim());
      for (let i = 1; i < lines.length; i++) {
        const values = splitCsvLine(lines[i]);
        const row = {};
        headers.forEach((h, idx) => row[h] = values[idx] || '');
        rows.push(row);
      }
      return rows;
    }

    function splitCsvLine(line) {
      const out = [];
      let cur = '', inQ = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; continue; }
        if (ch === '"') { inQ = !inQ; continue; }
        if (ch === ',' && !inQ) { out.push(cur); cur = ''; continue; }
        cur += ch;
      }
      out.push(cur);
      return out.map(s => s.trim());
    }

    function getActiveMatchingDriver(dev) {
      const list = dev.matchingDrivers || [];
      return list.find(m => { const s = (m.status || '').toLowerCase(); return s.includes('best ranked') || s.includes('installed'); }) || list[0] || null;
    }

    function getMatchedPnpDevices(d) {
      if (!d) return [];
      const target = d.publishedName.toLowerCase();
      return pnpDevices.value.filter(dev => dev.matchingDrivers.some(m => m.name === target)).map(dev => {
        const m = dev.matchingDrivers.find(x => x.name === target) || {};
        return { ...dev, specificInfStatus: m.status, specificInfVersion: m.ver, specificInfDate: m.date, specificInfSigner: m.signer };
      });
    }

    function getProblemData(instanceId) {
      return problemDevicesCombined.value.find(pd => (pd.pnpId || pd.instanceId || pd.InstanceId || '').toLowerCase() === (instanceId || '').toLowerCase());
    }

    function checkOemStatus(d) {
      const matches = getMatchedPnpDevices(d);
      const hasDevice = matches.length > 0;
      const isInstalled = hasDevice && matches.some(dev => { const s = (dev.specificInfStatus || '').toLowerCase(); return s.includes('best ranked') || s.includes('installed'); });
      const isProblem = matches.some(dev => !!getProblemData(dev.instanceId));
      return { isInstalled, isProblem, hasDevice };
    }

    function getSignerSummary(d) { const signers = [...new Set(getMatchedPnpDevices(d).map(m => m.specificInfSigner).filter(Boolean))]; return signers.length ? signers.join(' | ') : 'N/A (No matched device)'; }
    function getCatalogFileName(d) { const full = catalogMap.value[((d && d.publishedName) || '').toLowerCase()] || ''; if (!full) return 'N/A'; const normalized = full.replace(/\\/g, '/'); const name = normalized.split('/').pop() || full; return /\.cat$/i.test(name) ? name : name || 'N/A'; }
    function isWhqlSigner(signer) { return /Microsoft Windows Hardware Compatibility Publisher/i.test(signer || ''); }
    function isNonWhql(d) { const signers = getMatchedPnpDevices(d).map(m => m.specificInfSigner).filter(Boolean); return signers.length > 0 && signers.some(s => !isWhqlSigner(s)); }
    function statusLabel(d) { const st = checkOemStatus(d); return st.hasDevice ? (st.isInstalled ? 'INSTALLED' : 'OUTRANKED') : 'NO DEVICE'; }
    function badgeClass(label) { if (label === 'INSTALLED') return 'bg-emerald-100 text-emerald-700'; if (label === 'NO DEVICE') return 'bg-amber-100 text-amber-700'; if (label === 'OUTRANKED') return 'bg-yellow-100 text-yellow-700'; return 'bg-slate-100 text-slate-700'; }
    function driverStatusClass(status) { const s = (status || '').toLowerCase(); if (s.includes('best ranked') || s.includes('installed')) return 'bg-emerald-100 text-emerald-700'; if (!s) return 'bg-slate-100 text-slate-700'; return 'bg-red-100 text-red-700'; }
    function collectionBadgeClass(value) { const v = (value || '').toUpperCase(); if (v === 'OK') return 'bg-emerald-100 text-emerald-700'; if (v === 'NOT_FOUND' || v === 'SKIP') return 'bg-amber-100 text-amber-700'; if (v === 'FAIL' || v === 'EMPTY' || v === 'TIMEOUT') return 'bg-red-100 text-red-700'; return 'bg-slate-100 text-slate-700'; }

    function analyzeDriver(d) {
      const status = checkOemStatus(d), matches = getMatchedPnpDevices(d), issues = [];
      if (!status.hasDevice) issues.push({ level: 'info', text: 'No bound device (ORPHAN)' });
      if (isNonWhql(d)) issues.push({ level: 'warn', text: 'Non-WHQL driver (potential risk)' });
      matches.forEach(dev => { const problem = getProblemData(dev.instanceId); if (problem) issues.push({ level: 'error', text: `Device error: ${problem.error || problem.problem || problem.Problem || problem.ConfigManagerErrorCode}` }); });
      if (status.hasDevice && !status.isInstalled) issues.push({ level: 'warn', text: 'Driver is outranked (not active)' });
      return issues;
    }

    function formatRegValue(key, value) {
      if (value == null || value === '') return 'N/A';
      if (!showDecodedReg.value) return value;
      if (key === 'UBR') { const n = parseInt(String(value), 16); return Number.isNaN(n) ? value : String(n); }
      if (key === 'InstallDate') { const n = parseInt(String(value), 16); if (Number.isNaN(n)) return value; return new Date(n * 1000).toLocaleString(); }
      if (key === 'InstallTime') { const n = parseInt(String(value), 16); return Number.isNaN(n) ? value : String(n); }
      return value;
    }

    function getDeviceHuntInfo(rawId) {
      if (!rawId) return null;
      const id = String(rawId).toUpperCase();
      const pci = id.match(/^PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})/);
      if (pci) return { type: 'pci', vendor: pci[1], device: pci[2], url: `https://devicehunt.com/view/type/pci/vendor/${pci[1]}/device/${pci[2]}` };
      const usb = id.match(/^USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})/);
      if (usb) return { type: 'usb', vendor: usb[1], device: usb[2], url: `https://devicehunt.com/view/type/usb/vendor/${usb[1]}/device/${usb[2]}` };
      return null;
    }

    function isGhostProblemRecord(d) {
      const s = [d && d.Problem, d && d.problem, d && d.ConfigManagerErrorCode, d && d.error, d && d.status, d && d.Status].filter(Boolean).join(' ');
      return /CM_PROB_PHANTOM/i.test(s);
    }

    function isDeviceClassCollapsed(className) {
      return collapsedDeviceClasses.value[className] !== false;
    }

    function toggleDeviceClass(className) {
      collapsedDeviceClasses.value = { ...collapsedDeviceClasses.value, [className]: !isDeviceClassCollapsed(className) };
    }

    function isHighlightedDevice(dev) { if (!selectedOem.value) return false; return (dev.activeDriver || '').toLowerCase() === (selectedOem.value.publishedName || '').toLowerCase(); }
    function getDriverObjectByName(name) { if (!name) return null; return dismDrivers.value.find(d => d.publishedName.toLowerCase() === String(name).toLowerCase()) || null; }
    function openDriverFromDevice(dev) { const d = getDriverObjectByName(dev.activeDriver); if (d) { selectedOem.value = d; selectedPanel.value = 'driver'; } }
    function normalizeProblem(...vals) { const s = vals.filter(Boolean).join(' '); if (!s || /CM_PROB_NONE/i.test(s)) return ''; return s; }
    function isProblemStatus(status, problem, cm) { const s = [status, problem, cm].filter(Boolean).join(' '); return !!s && !/\bOK\b/i.test(status || '') && !/CM_PROB_NONE/i.test(s); }
    function firstMeaningfulLine(text) { return (text || '').split(/\r?\n/).map(s => s.trim()).find(Boolean) || 'Loaded'; }
    function getDxDiagHeadline(text) { const model = (text.match(/System Model:\s*(.+)/i) || [])[1]; const os = (text.match(/Operating System:\s*(.+)/i) || [])[1]; return [model, os].filter(Boolean).join(' | ') || 'Display / audio diagnostics available'; }

    return { dragOver, loadedFileNames, selectedPanel, keyword, filterProvider, filterStatus, selectedOem, selectedDevice, deviceKeyword, deviceOnlyProblem, deviceOnlyHighlighted, selectedProblemTab, collapsedDeviceClasses, dismDrivers, pnpDevices, pnpCsvDevices, problemDevices, pnpProblemDevices, pnpProblemCsvDevices, catalogMap, sysInfo, systemSummary, collectionStatus, runLogText, rawWindowsVersionReg, winRegParsed, statusOptions, hasData, providers, systemHeadline, secureBootClass, problemDevicesCombined, ghostDevices, summaryCards, collectionOkCount, collectionMissingCount, systemHealthLoadedCount, systemInfoGeneratedTime, hardwareSummaryRows, finalFilteredDrivers, matchedPnpDevices, fullDeviceList, filteredDeviceGroups, platformHealthCards, rawDxDiagText, rawPowerCfgA, rawPowerCfgRequests, rawPowerCfgLastWake, rawPowerCfgWakeArmed, rawSleepStudyText, rawEnergyReportText, displayAudioCameraRows, usbTypecRows, vendorRows, hardwareInventory, platformConfigurationSections, platformConfigurationHeadline, resetTool, handleBatchUpload, handleDrop, checkOemStatus, statusLabel, badgeClass, getProblemData, getSignerSummary, isNonWhql, collectionBadgeClass, driverStatusClass, getCatalogFileName, jsonFilter, regFilter, filteredSystemSummary, filteredWinReg, onDragEnter, onDragOver, onDragLeave, analyzeDriver, showDecodedReg, formatRegValue, getDeviceHuntInfo, navClass, isHighlightedDevice, getDriverObjectByName, openDriverFromDevice, isGhostProblemRecord, isDeviceClassCollapsed, toggleDeviceClass, openFolderPicker, installedAppsWin32, installedAppsAppx, provisionedApps, startupApps, installedUpdates, servicesRows, scheduledTasksRows, showMicrosoftApps, combinedInstalledApps, filteredStartupApps, rawDefaultAppsText, rawPowerPlanText, rawIPConfigText, rawPnpInterfacesText, rawScheduledTasksText, operationsLogCards };
  }
}).mount('#app');
