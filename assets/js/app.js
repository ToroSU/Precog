window.addEventListener('dragover', function (e) { e.preventDefault(); });
window.addEventListener('drop', function (e) { e.preventDefault(); });

const { createApp, ref, computed, nextTick } = Vue;

createApp({
  setup() {
    const {
      asArray, cleanText, joinDetails, bytesToGB, normalizeAppKey,
      appDisplayName, appPublisher, isMicrosoftApp, appVersion,
      parseWindowsVersionReg, parseCsv, splitCsvLine, normalizeProblem,
      isProblemStatus, firstMeaningfulLine, getDxDiagHeadline, getDeviceHuntInfo
    } = window.PrecogUtils;

    const dragOver = ref(false);
    const dragCounter = ref(0);
    const loadedFileNames = ref([]);
    const loadedSourceName = ref('');
    const selectedPanel = ref('system');
    const deviceManagerView = ref('devices');
    const keyword = ref('');
    const driverFilterInput = ref(null);
    const filterProvider = ref('All');
    const filterStatus = ref('All');
    const selectedOem = ref(null);
    const selectedDevice = ref(null);
    const deviceKeyword = ref('');
    const deviceFilterInput = ref(null);
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
    const showMicrosoftApps = ref(false); // Legacy compatibility; Apps v2 uses appAudienceFilter.
    const appFilterKeyword = ref('');
    const appFilterInput = ref(null);
    const appPublisherFilter = ref('All');
    const appAudienceFilter = ref('Non-Microsoft');
    const startupAppsExpanded = ref(true);
    const rawDefaultAppsText = ref('');
    const rawPowerPlanText = ref('');
    const rawIPConfigText = ref('');
    const rawPnpInterfacesText = ref('');
    const rawScheduledTasksText = ref('');
    const pnpDeviceStatus = ref([]);
    const parentDeviceRows = ref([]);
    const expandedConnectionNodes = ref({});
    const activeSystemSection = ref('overview');

    // Debug evidence: raw published OEM INF text collected by Dowsing.
    // Keyed by published name, e.g. "oem0.inf".
    const oemInfContents = ref({});
    const infViewerOpen = ref(false);
    const infViewerName = ref('');
    const infViewerContent = ref('');
    const infViewerSearch = ref('');
    const infViewerCopyLabel = ref('Copy');


    const statusOptions = ['All', 'Installed', 'No Device', 'Problem'];

    const hasData = computed(() => !!(dismDrivers.value.length || pnpDevices.value.length || pnpCsvDevices.value.length || Object.keys(systemSummary.value).length || Object.keys(sysInfo.value).length || Object.keys(hardwareInventory.value).length));

    function navClass(panel) {
      return ['px-4 py-2 rounded-xl border text-sm font-semibold', selectedPanel.value === panel ? 'bg-slate-900 text-white border-slate-900' : 'bg-white hover:bg-slate-50'].join(' ');
    }

    function normalizedOemInfName(value) {
      const name = String(value || '').split('/').pop().trim().toLowerCase();
      return /^oem\d+\.inf$/i.test(name) ? name : '';
    }

    function hasOriginalInfContent(driver) {
      const key = normalizedOemInfName(driver && driver.publishedName);
      return !!(key && Object.prototype.hasOwnProperty.call(oemInfContents.value, key));
    }

    function openInfViewer(driver) {
      const key = normalizedOemInfName(driver && driver.publishedName);
      if (!key || !Object.prototype.hasOwnProperty.call(oemInfContents.value, key)) return;
      infViewerName.value = key;
      infViewerContent.value = oemInfContents.value[key] || '';
      infViewerSearch.value = '';
      infViewerCopyLabel.value = 'Copy';
      infViewerOpen.value = true;
      nextTick(() => {
        const input = document.getElementById('infViewerSearchInput');
        if (input) input.focus();
      });
    }

    function closeInfViewer() {
      infViewerOpen.value = false;
      infViewerSearch.value = '';
    }

    async function copyInfContent() {
      const text = infViewerContent.value || '';
      if (!text) return;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const ta = document.createElement('textarea');
          ta.value = text;
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          document.execCommand('copy');
          ta.remove();
        }
        infViewerCopyLabel.value = 'Copied';
      } catch (err) {
        console.error('Copy INF content failed', err);
        infViewerCopyLabel.value = 'Copy failed';
      }
      window.setTimeout(() => { infViewerCopyLabel.value = 'Copy'; }, 1400);
    }

    function escapeHtml(value) {
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    const infViewerRenderedContent = computed(() => {
      const raw = infViewerContent.value || '';
      const query = (infViewerSearch.value || '').trim();
      if (!query) return escapeHtml(raw);

      const escapedRaw = escapeHtml(raw);
      const escapedQuery = escapeHtml(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (!escapedQuery) return escapedRaw;

      try {
        return escapedRaw.replace(new RegExp(escapedQuery, 'gi'), match => `<mark class="inf-search-hit">${match}</mark>`);
      } catch (_) {
        return escapedRaw;
      }
    });

    const infViewerMatchCount = computed(() => {
      const raw = infViewerContent.value || '';
      const query = (infViewerSearch.value || '').trim();
      if (!raw || !query) return 0;
      let count = 0;
      let pos = 0;
      const haystack = raw.toLowerCase();
      const needle = query.toLowerCase();
      while ((pos = haystack.indexOf(needle, pos)) !== -1) {
        count += 1;
        pos += Math.max(needle.length, 1);
      }
      return count;
    });

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

    const windowsReleaseLabel = computed(() => {
      const displayVersion = winRegParsed.value.DisplayVersion || winRegParsed.value.ReleaseId || '';
      const build = winRegParsed.value.CurrentBuild || systemSummary.value.OSBuild || '';
      const ubrRaw = winRegParsed.value.UBR || '';
      const ubr = ubrRaw ? formatRegValue('UBR', ubrRaw) : '';
      const fullBuild = [build, ubr].filter(Boolean).join('.');
      if (displayVersion && fullBuild) return `${displayVersion} · Build ${fullBuild}`;
      if (displayVersion) return displayVersion;
      if (fullBuild) return `Build ${fullBuild}`;
      return systemHeadline.value.build || 'N/A';
    });

    const secureBootClass = computed(() => {
      const v = (systemHeadline.value.secureBoot || '').toLowerCase();
      if (v.includes('on')) return 'text-emerald-600';
      if (v.includes('off')) return 'text-amber-600';
      return 'text-slate-700';
    });

    const pnpDeviceStatusMap = computed(() => {
      const map = new Map();
      pnpDeviceStatus.value.forEach(item => {
        const id = item.InstanceId || item.instanceId || item.DeviceInstanceId || '';
        if (id) map.set(id.toLowerCase(), item);
      });
      return map;
    });

    function getDeviceStatus(instanceId) {
      if (!instanceId) return null;
      return pnpDeviceStatusMap.value.get(String(instanceId).toLowerCase()) || null;
    }

    function scrollSystemSection(sectionId) {
      activeSystemSection.value = sectionId;
      requestAnimationFrame(() => {
        const el = document.getElementById('system-section-' + sectionId);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    }

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
      return { totalDrivers: dismDrivers.value.length, installed, storeOnly, problem: problemDevicesCombined.value.length + nonWhql, nonWhql };
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
          version: '',
          deviceStatus: getDeviceStatus(id)
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
          version: old.version || '',
          deviceStatus: getDeviceStatus(old.instanceId || id)
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
          version: active ? active.ver : (base.version || ''),
          deviceStatus: getDeviceStatus(id)
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


    const connectionTopology = computed(() => {
      const detailsById = new Map(
        fullDeviceList.value
          .filter(dev => dev && dev.instanceId)
          .map(dev => [String(dev.instanceId).toLowerCase(), dev])
      );

      const nodes = new Map();

      function ensureNode(instanceId, fallback = {}) {
        const id = String(instanceId || '').trim();
        if (!id) return null;
        const key = id.toLowerCase();
        if (!nodes.has(key)) {
          const detail = detailsById.get(key);
          nodes.set(key, {
            key,
            instanceId: id,
            parentKey: '',
            parentInstanceId: '',
            name: (detail && detail.name) || fallback.name || fallback.FriendlyName || id,
            className: (detail && detail.className) || fallback.className || fallback.Class || 'Unknown',
            status: (detail && detail.status) || fallback.status || fallback.Status || '',
            problem: (detail && detail.problem) || normalizeProblem(fallback.Problem || fallback.ConfigManagerErrorCode || ''),
            isProblem: detail ? !!detail.isProblem : isProblemStatus(fallback.Status, fallback.Problem, fallback.ConfigManagerErrorCode),
            isGhost: detail ? !!detail.isGhost : isGhostProblemRecord(fallback),
            device: detail || null,
            children: [],
            synthetic: !detail
          });
        } else {
          const node = nodes.get(key);
          const detail = detailsById.get(key);
          if (detail) {
            node.device = detail;
            node.name = detail.name || node.name;
            node.className = detail.className || node.className;
            node.status = detail.status || node.status;
            node.problem = detail.problem || node.problem;
            node.isProblem = !!detail.isProblem;
            node.isGhost = !!detail.isGhost;
            node.synthetic = false;
          }
        }
        return nodes.get(key);
      }

      parentDeviceRows.value.forEach(row => {
        const childId = row.InstanceId || row.instanceId || '';
        if (!childId) return;

        const node = ensureNode(childId, row);
        if (!node) return;

        const parentId = String(row.ParentInstanceId || row.parentInstanceId || '').trim();
        if (parentId && parentId.toLowerCase() !== node.key) {
          const parent = ensureNode(parentId, { FriendlyName: parentId, Class: 'Connection Root' });
          if (parent) {
            node.parentKey = parent.key;
            node.parentInstanceId = parent.instanceId;
          }
        }
      });

      // Include loaded devices even if the parent collector did not return a row for one.
      fullDeviceList.value.forEach(dev => {
        if (dev && dev.instanceId) ensureNode(dev.instanceId, dev);
      });

      nodes.forEach(node => { node.children = []; });
      const roots = [];

      nodes.forEach(node => {
        const parent = node.parentKey ? nodes.get(node.parentKey) : null;
        if (parent && parent.key !== node.key) {
          parent.children.push(node);
        } else {
          roots.push(node);
        }
      });

      const sortNodes = list => {
        list.sort((a, b) =>
          String(a.className || '').localeCompare(String(b.className || '')) ||
          String(a.name || '').localeCompare(String(b.name || '')) ||
          String(a.instanceId || '').localeCompare(String(b.instanceId || ''))
        );
        list.forEach(node => sortNodes(node.children));
      };
      sortNodes(roots);

      return {
        nodes,
        roots,
        edgeCount: [...nodes.values()].filter(node => !!node.parentKey).length,
        collectedCount: parentDeviceRows.value.length
      };
    });

    function connectionNodeMatches(node) {
      if (!node) return false;
      const dev = node.device || node;
      if (deviceOnlyProblem.value && !node.isProblem) return false;
      if (deviceOnlyHighlighted.value && !isHighlightedDevice(dev)) return false;

      const q = deviceKeyword.value.toLowerCase();
      if (!q) return true;

      const text = [
        node.name,
        node.instanceId,
        node.parentInstanceId,
        node.className,
        node.status,
        node.problem,
        dev.activeDriver,
        dev.signer,
        ...(dev.hwids || [])
      ].filter(Boolean).join(' ').toLowerCase();

      return text.includes(q);
    }

    const connectionFilterActive = computed(() =>
      !!deviceKeyword.value || deviceOnlyProblem.value || deviceOnlyHighlighted.value
    );

    const connectionVisibleKeys = computed(() => {
      if (!connectionFilterActive.value) return null;

      const visible = new Set();
      const topology = connectionTopology.value;

      topology.nodes.forEach(node => {
        if (!connectionNodeMatches(node)) return;

        let current = node;
        const visited = new Set();
        while (current && !visited.has(current.key)) {
          visited.add(current.key);
          visible.add(current.key);
          current = current.parentKey ? topology.nodes.get(current.parentKey) : null;
        }
      });

      return visible;
    });

    function isConnectionExpanded(node, depth = 0) {
      if (!node) return false;
      if (connectionFilterActive.value) return true;
      if (Object.prototype.hasOwnProperty.call(expandedConnectionNodes.value, node.key)) {
        return !!expandedConnectionNodes.value[node.key];
      }
      // Give the user an immediately useful topology without flooding the page.
      return depth < 2;
    }

    function toggleConnectionNode(node, depth = 0) {
      if (!node || !node.children || !node.children.length) return;
      expandedConnectionNodes.value = {
        ...expandedConnectionNodes.value,
        [node.key]: !isConnectionExpanded(node, depth)
      };
    }

    const connectionTreeRows = computed(() => {
      if (!parentDeviceRows.value.length) return [];

      const rows = [];
      const visible = connectionVisibleKeys.value;
      const visited = new Set();

      function walk(node, depth) {
        if (!node || visited.has(node.key)) return;
        if (visible && !visible.has(node.key)) return;

        visited.add(node.key);
        rows.push({
          ...node,
          depth,
          hasChildren: !!(node.children && node.children.length),
          expanded: isConnectionExpanded(node, depth)
        });

        if (node.children && node.children.length && isConnectionExpanded(node, depth)) {
          node.children.forEach(child => walk(child, depth + 1));
        }
      }

      connectionTopology.value.roots.forEach(root => walk(root, 0));
      return rows;
    });

    function getParentConnection(instanceId) {
      const key = String(instanceId || '').toLowerCase();
      if (!key) return null;
      const node = connectionTopology.value.nodes.get(key);
      if (!node || !node.parentKey) return null;
      return connectionTopology.value.nodes.get(node.parentKey) || null;
    }

    function selectConnectionDevice(node) {
      if (!node) return;
      if (node.device) {
        selectedDevice.value = node.device;
        return;
      }

      selectedDevice.value = {
        name: node.name || 'Unknown Device',
        instanceId: node.instanceId || '',
        className: node.className || 'Unknown',
        status: node.status || '',
        problem: node.problem || '',
        isProblem: !!node.isProblem,
        isGhost: !!node.isGhost,
        activeDriver: '',
        activeDriverStatus: '',
        signer: '',
        version: '',
        hwids: [],
        matchingDrivers: [],
        deviceStatus: getDeviceStatus(node.instanceId)
      };
    }

    const disabledDevices = computed(() => fullDeviceList.value.filter(dev => {
      const statusText = [
        dev.status,
        dev.problem,
        dev.deviceStatus && dev.deviceStatus.ProblemName,
        dev.deviceStatus && dev.deviceStatus.ProblemCode,
        dev.deviceStatus && dev.deviceStatus.ConfigManagerErrorCode
      ].filter(v => v !== undefined && v !== null).join(' ');
      return /CM_PROB_DISABLED|\bdisabled\b/i.test(statusText) || /(^|\D)22(\D|$)/.test(statusText);
    }));

    const powerRequestStatus = computed(() => {
      const text = rawPowerCfgRequests.value.trim();
      if (!text) return 'Not Available';
      const normalized = text.toLowerCase();
      const hasActiveRequest = /\[[^\]]+\]/.test(text) ||
        /(?:display|system|awaymode|execution|perfboost|activelockscreen):\s*(?!none\b)[^\r\n]+/i.test(text);
      if (hasActiveRequest) return 'Warning';
      if (normalized.includes('none') || normalized.includes('無')) return 'Available';
      return 'Available';
    });

    function healthStatusClass(status) {
      if (status === 'Available') return 'bg-emerald-100 text-emerald-700';
      if (status === 'Warning') return 'bg-amber-100 text-amber-700';
      if (status === 'Error') return 'bg-red-100 text-red-700';
      return 'bg-slate-100 text-slate-600';
    }

    const platformHealthCards = computed(() => {
      const wakeAvailable = !!(rawPowerCfgLastWake.value || rawPowerCfgWakeArmed.value);
      const reportCount = [rawSleepStudyText.value, rawEnergyReportText.value].filter(Boolean).length;
      return [
        {
          title: 'Sleep Capability',
          status: rawPowerCfgA.value ? 'Available' : 'Not Available',
          value: rawPowerCfgA.value ? 'Sleep states collected' : 'No capability data',
          detail: rawPowerCfgA.value ? firstMeaningfulLine(rawPowerCfgA.value) : 'powercfg /a was not found in the loaded source.',
          cardClass: rawPowerCfgA.value ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50',
          labelClass: rawPowerCfgA.value ? 'text-emerald-600' : 'text-slate-400'
        },
        {
          title: 'Power Requests',
          status: powerRequestStatus.value,
          value: powerRequestStatus.value === 'Warning' ? 'Active request detected' : (rawPowerCfgRequests.value ? 'No blocking request detected' : 'No request data'),
          detail: rawPowerCfgRequests.value ? firstMeaningfulLine(rawPowerCfgRequests.value) : 'powercfg /requests was not found in the loaded source.',
          cardClass: powerRequestStatus.value === 'Warning' ? 'border-amber-200 bg-amber-50' : (rawPowerCfgRequests.value ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50'),
          labelClass: powerRequestStatus.value === 'Warning' ? 'text-amber-600' : (rawPowerCfgRequests.value ? 'text-emerald-600' : 'text-slate-400')
        },
        {
          title: 'Wake Information',
          status: wakeAvailable ? 'Available' : 'Not Available',
          value: wakeAvailable ? 'Wake data collected' : 'No wake data',
          detail: rawPowerCfgLastWake.value ? firstMeaningfulLine(rawPowerCfgLastWake.value) : (rawPowerCfgWakeArmed.value ? firstMeaningfulLine(rawPowerCfgWakeArmed.value) : 'Wake source and wake-armed data were not found.'),
          cardClass: wakeAvailable ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50',
          labelClass: wakeAvailable ? 'text-emerald-600' : 'text-slate-400'
        },
        {
          title: 'Power Reports',
          status: reportCount ? 'Available' : 'Not Available',
          value: `${reportCount} / 2 reports available`,
          detail: 'SleepStudy and Energy Report availability.',
          cardClass: reportCount ? 'border-emerald-200 bg-emerald-50' : 'border-slate-200 bg-slate-50',
          labelClass: reportCount ? 'text-emerald-600' : 'text-slate-400'
        }
      ];
    });



















    function normalizeAppPublisher(name, rawPublisher, packageName = '') {
      const raw = cleanText(rawPublisher);
      const haystack = [name, raw, packageName].filter(Boolean).join(' ').toLowerCase();

      // Curated normalization for common ODM/OEM software publishers.
      if (/microsoft|windowsapps|edgeupdate|onedrive|securityhealth/.test(haystack)) return 'Microsoft';
      if (/giga[- ]?byte|gigabyte|gimate|aorus/.test(haystack)) return 'GIGABYTE';
      if (/nvidia/.test(haystack)) return 'NVIDIA';
      if (/advancedmicrodevices|advanced micro devices|amdradeon|amd radeon|\bamd\b/.test(haystack)) return 'AMD';
      if (/realtek/.test(haystack)) return 'Realtek';
      if (/dolby/.test(haystack)) return 'Dolby';
      if (/a-volute|avolute|nahimic/.test(haystack)) return 'A-Volute';
      if (/intel/.test(haystack)) return 'Intel';

      // Appx certificate publishers can be GUID-like CN values. Keep those out of the main UI.
      if (!raw) return 'Other / Unknown';
      const guidCn = /^CN\s*=\s*[\{(]?[0-9a-f-]{20,}[\})]?$/i.test(raw);
      if (guidCn) return 'Other / Unknown';

      // For human-readable certificate subjects prefer O=, then CN=.
      const orgMatch = raw.match(/(?:^|,)\s*O\s*=\s*"?([^",]+(?:\s+[^",]+)*)"?/i);
      if (orgMatch && orgMatch[1]) return orgMatch[1].trim();
      const cnMatch = raw.match(/^CN\s*=\s*"?([^",]+(?:\s+[^",]+)*)"?/i);
      if (cnMatch && cnMatch[1] && !/^[0-9a-f-]{20,}$/i.test(cnMatch[1].trim())) return cnMatch[1].trim();
      return raw;
    }

    const allCombinedInstalledApps = computed(() => {
      const map = new Map();

      function addApp(row, source) {
        const name = appDisplayName(row);
        const version = appVersion(row);
        const rawPublisher = appPublisher(row);
        const family = row.PackageFamilyName || row.PackageName || row.PackageFullName || row.PSChildName || '';
        const packageName = row.PackageFullName || row.PackageName || row.PackageFamilyName || '';
        const key = normalizeAppKey(name || family);
        if (!key) return;

        const current = map.get(key);
        const displayPublisher = normalizeAppPublisher(name, rawPublisher, packageName || family);
        const item = {
          name,
          version,
          publisher: displayPublisher,
          displayPublisher,
          rawPublisher,
          source,
          packageName,
          installLocation: row.InstallLocation || '',
          raw: row,
          isMicrosoft: displayPublisher === 'Microsoft'
        };

        if (!current) {
          map.set(key, item);
        } else {
          const sources = new Set(String(current.source).split(' + ').concat(source));
          current.source = [...sources].filter(Boolean).join(' + ');
          current.version = current.version || version;
          current.rawPublisher = current.rawPublisher || rawPublisher;
          current.packageName = current.packageName || item.packageName;
          current.installLocation = current.installLocation || item.installLocation;
          if (current.displayPublisher === 'Other / Unknown' && displayPublisher !== 'Other / Unknown') {
            current.displayPublisher = displayPublisher;
            current.publisher = displayPublisher;
          }
          current.isMicrosoft = current.displayPublisher === 'Microsoft';
        }
      }

      installedAppsWin32.value.forEach(r => addApp(r, 'Win32'));
      installedAppsAppx.value.forEach(r => addApp(r, 'Appx'));
      provisionedApps.value.forEach(r => addApp(r, 'Provisioned'));

      return [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
    });

    const appPublisherOptions = computed(() => {
      const preferred = ['GIGABYTE', 'AMD', 'NVIDIA', 'Intel', 'Realtek', 'Dolby', 'A-Volute', 'Microsoft', 'Other / Unknown'];
      const found = [...new Set(allCombinedInstalledApps.value.map(app => app.displayPublisher).filter(Boolean))];
      return found.sort((a, b) => {
        const ai = preferred.indexOf(a), bi = preferred.indexOf(b);
        if (ai !== -1 || bi !== -1) {
          if (ai === -1) return 1;
          if (bi === -1) return -1;
          return ai - bi;
        }
        return a.localeCompare(b);
      });
    });

    const combinedInstalledApps = computed(() => {
      const q = appFilterKeyword.value.trim().toLowerCase();
      return allCombinedInstalledApps.value.filter(app => {
        const audienceMatch = appAudienceFilter.value === 'All'
          || (appAudienceFilter.value === 'Microsoft' ? app.isMicrosoft : !app.isMicrosoft);
        const publisherMatch = appPublisherFilter.value === 'All' || app.displayPublisher === appPublisherFilter.value;
        const searchText = [
          app.name, app.version, app.displayPublisher, app.rawPublisher, app.source,
          app.packageName, app.installLocation
        ].filter(Boolean).join(' ').toLowerCase();
        const keywordMatch = !q || searchText.includes(q);
        return audienceMatch && publisherMatch && keywordMatch;
      });
    });

    function setAppAudience(value) {
      appAudienceFilter.value = value;
      appPublisherFilter.value = 'All';
    }

    function clearAppFilter() {
      appFilterKeyword.value = '';
      nextTick(() => appFilterInput.value?.focus());
    }

    const allStartupApps = computed(() => startupApps.value
      .map(r => {
        const displayPublisher = normalizeAppPublisher(r.Name || '', r.Command || '', r.Location || '');
        return { ...r, displayPublisher, isMicrosoft: displayPublisher === 'Microsoft' };
      })
      .sort((a, b) => String(a.Name || '').localeCompare(String(b.Name || ''))));

    // Startup is a behavior view and intentionally stays independent from Installed Apps filters.
    const filteredStartupApps = computed(() => allStartupApps.value);

    const appsOverviewCards = computed(() => [
      { title: 'Installed Applications', count: allCombinedInstalledApps.value.length, subtitle: 'Merged and deduplicated' },
      { title: 'Startup Applications', count: allStartupApps.value.length, subtitle: 'Configured startup entries' },
      { title: 'Non-Microsoft Applications', count: allCombinedInstalledApps.value.filter(app => !app.isMicrosoft).length, subtitle: 'OEM and third-party software' },
      { title: 'Microsoft Applications', count: allCombinedInstalledApps.value.filter(app => app.isMicrosoft).length, subtitle: 'Microsoft software' }
    ]);

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
      sections.push({ title: 'CPU', badge: cpuRows.length ? `${cpuRows.length}` : '0', rows: cpuRows, wide: false });

      const mem = hw.Memory || {};
      const memoryRows = asArray(mem.Modules).map(m => makeConfigRow(
        [m.Manufacturer, m.PartNumber].filter(Boolean).join(' ') || m.Slot || m.Bank,
        [m.CapacityGB ? `${m.CapacityGB} GB` : bytesToGB(m.Capacity), m.ConfiguredClockSpeedMHz ? `${m.ConfiguredClockSpeedMHz} MHz` : (m.ConfiguredClockSpeed ? `${m.ConfiguredClockSpeed} MHz` : (m.SpeedMHz ? `${m.SpeedMHz} MHz` : (m.Speed ? `${m.Speed} MHz` : ''))), m.Slot || m.Bank],
        [m.SerialNumber]
      ));
      sections.push({ title: 'Memory', badge: mem.TotalGB ? `${mem.TotalGB} GB` : `${memoryRows.length}`, rows: memoryRows, wide: false });

      const storage = hw.Storage || {};
      const storageRows = asArray(storage.PhysicalDisks).map(d => makeConfigRow(
        d.FriendlyName || d.Model,
        [d.SizeGB ? `${d.SizeGB} GB` : bytesToGB(d.Size), d.BusType || d.InterfaceType, d.MediaType, d.HealthStatus],
        [d.SerialNumber]
      ));
      sections.push({ title: 'Storage', badge: storageRows.length ? `${storageRows.length}` : '0', rows: storageRows, wide: true });

      const display = hw.Display || {};
      const monitorRows = asArray(display.Monitors).map(m => makeConfigRow(
        m.DisplayName || m.UserFriendlyName || m.Model || [m.Manufacturer, m.PanelCode || m.ProductCode || m.ManufacturerCode].filter(Boolean).join(' ') || 'Monitor',
        [m.Active === true ? 'Active' : (m.Active === false ? 'Inactive' : ''), m.Manufacturer || m.ManufacturerCode, m.Model || m.PanelCode || m.ProductCode],
        [m.InstanceName]
      ));
      sections.push({ title: 'Display / Panel', badge: monitorRows.length ? `${monitorRows.length}` : '0', rows: monitorRows, wide: false });

      const gpuRows = asArray(hw.Graphics).map(g => makeConfigRow(
        g.Name,
        [g.DriverVersion, g.VideoProcessor, g.AdapterRAMGB ? `${g.AdapterRAMGB} GB VRAM` : '', g.CurrentHorizontalResolution && g.CurrentVerticalResolution ? `${g.CurrentHorizontalResolution}x${g.CurrentVerticalResolution}` : ''],
        [g.PNPDeviceID]
      ));
      sections.push({ title: 'Graphics', badge: gpuRows.length ? `${gpuRows.length}` : '0', rows: gpuRows, wide: true });

      const system = hw.System || {};
      const firmwareRows = [makeConfigRow(
        [system.Manufacturer, system.BaseBoardProduct].filter(Boolean).join(' ') || system.Model || 'Motherboard / Firmware',
        [system.BaseBoardVersion ? `Board ${system.BaseBoardVersion}` : '', system.BIOSVersion ? `BIOS ${system.BIOSVersion}` : '', system.BIOSReleaseDate ? `Released ${system.BIOSReleaseDate}` : ''],
        [system.SystemSKU, system.SecureBoot ? `Secure Boot: ${system.SecureBoot}` : '']
      )].filter(r => r.name !== 'Unknown' || r.detail || r.meta);
      sections.push({ title: 'Motherboard / Firmware', badge: firmwareRows.length ? `${firmwareRows.length}` : '0', rows: firmwareRows, wide: false });

      const network = hw.Network || {};
      const lanSource = asArray(network.LAN).length ? asArray(network.LAN) : asArray(network.Adapters).filter(n => String(n.Type || '').toUpperCase() === 'LAN');
      const networkRows = lanSource.map(n => makeConfigRow(
        n.DisplayName || n.InterfaceDescription || n.NetConnectionID || n.Name,
        [n.Type || 'LAN', n.Status, n.LinkSpeed, n.Manufacturer, n.NetEnabled === true ? 'Enabled' : (n.NetEnabled === false ? 'Disabled' : '')],
        [n.MacAddress || n.MACAddress, n.InterfaceGuid, n.PNPDeviceID]
      ));
      sections.push({ title: 'Wired Network', badge: networkRows.length ? `${networkRows.length}` : '0', rows: networkRows, wide: true });

      const wlanSource = asArray(network.WLAN).length ? asArray(network.WLAN) : asArray(network.Adapters).filter(n => String(n.Type || '').toUpperCase() === 'WLAN');
      const wirelessRows = wlanSource.map(n => makeConfigRow(
        n.DisplayName || n.InterfaceDescription || n.NetConnectionID || n.Name,
        ['WLAN', n.Status, n.LinkSpeed, n.Manufacturer, n.NetEnabled === true ? 'Enabled' : (n.NetEnabled === false ? 'Disabled' : '')],
        [n.MacAddress || n.MACAddress, n.InterfaceGuid, n.PNPDeviceID]
      ));
      asArray(network.Bluetooth).forEach(b => wirelessRows.push(makeConfigRow(
        b.FriendlyName || b.Name || 'Bluetooth Adapter',
        ['Bluetooth', b.Status, b.Problem],
        [b.InstanceId]
      )));
      sections.push({ title: 'Wireless', badge: wirelessRows.length ? `${wirelessRows.length}` : '0', rows: wirelessRows, wide: false });

      // System Configuration is a functional inventory, not a raw PnP dump.
      // Keep only devices that clearly represent the requested hardware function.
      const audioRows = asArray(hw.Audio)
        .filter(a => {
          const name = cleanText(a.FriendlyName || a.Name).toLowerCase();
          const cls = cleanText(a.Class).toLowerCase();
          const id = cleanText(a.InstanceId).toLowerCase();
          const clearlyAudio = /audio|sound|smart sound|realtek|dolby|hdaudio|intelaudio/.test(`${name} ${cls} ${id}`);
          const unrelated = /high precision event timer|system timer|enumerator|root complex|pci express root|acpi x64-based pc/.test(name);
          return clearlyAudio && !unrelated;
        })
        .map(a => makeConfigRow(
          a.FriendlyName || a.Name,
          [a.Status, a.Problem],
          [a.InstanceId]
        ));
      sections.push({ title: 'Audio', badge: audioRows.length ? `${audioRows.length}` : '0', rows: audioRows, wide: audioRows.length > 2 });

      const cameraRows = asArray(hw.Camera)
        .filter(c => {
          const name = cleanText(c.FriendlyName || c.Name).toLowerCase();
          const cls = cleanText(c.Class).toLowerCase();
          const id = cleanText(c.InstanceId).toLowerCase();
          const clearlyCamera = /camera|webcam|imaging|image/.test(`${name} ${cls}`) || cls === 'camera' || cls === 'image';
          const genericChildOrPlatform = /acpi x64-based pc|i2c hid device|usb input device|hid-compliant|composite device|root hub|enumerator/.test(name);
          const cameraIdentity = /camera|webcam|ir camera|rgb camera/.test(name) || /camera|image/.test(cls) || /vid_[0-9a-f]{4}.*pid_[0-9a-f]{4}/.test(id);
          return clearlyCamera && cameraIdentity && !genericChildOrPlatform;
        })
        .map(c => makeConfigRow(
          c.FriendlyName || c.Name,
          [c.Status, c.Problem],
          [c.InstanceId]
        ));
      sections.push({ title: 'Camera', badge: cameraRows.length ? `${cameraRows.length}` : '0', rows: cameraRows, wide: false });

      const batteryRows = asArray(hw.Battery).map(b => makeConfigRow(
        b.Name || b.DeviceID,
        [b.Manufacturer, b.EstimatedChargeRemaining !== null && b.EstimatedChargeRemaining !== undefined ? `${b.EstimatedChargeRemaining}%` : '', b.BatteryStatus ? `Status ${b.BatteryStatus}` : ''],
        [b.DeviceID]
      ));
      sections.push({ title: 'Battery', badge: batteryRows.length ? `${batteryRows.length}` : '0', rows: batteryRows, wide: false });

      const input = hw.Input || {};
      const inputRows = asArray(input.HID).slice(0, 50).map(i => makeConfigRow(
        i.FriendlyName,
        [i.Class, i.Status, i.Problem],
        [i.InstanceId]
      ));
      sections.push({ title: 'Input / HID', badge: inputRows.length ? `${inputRows.length}` : '0', rows: inputRows, wide: true });

      const usbRows = asArray(hw.USB).slice(0, 80).map(u => makeConfigRow(
        u.FriendlyName,
        [u.Class, u.Status, u.Problem],
        [u.InstanceId]
      ));
      sections.push({ title: 'USB', badge: usbRows.length ? `${usbRows.length}` : '0', rows: usbRows, wide: true });

      const tpm = asArray(hw.Security && hw.Security.TPM)[0] || asArray(hw.TPM)[0];
      const securityRows = tpm ? [makeConfigRow('TPM', [tpm.TpmPresent ? 'Present' : 'Not present', tpm.TpmReady ? 'Ready' : 'Not ready', tpm.ManufacturerIdTxt, tpm.SpecVersion], [tpm.ManufacturerVersion])] : [];
      sections.push({ title: 'Security', badge: securityRows.length ? `${securityRows.length}` : '0', rows: securityRows, wide: false });

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
    function handleBatchUpload(e) { const files = Array.from((e.target && e.target.files) || []); if (files.length) processInputFiles(files); if (e && e.target) e.target.value = ""; }
    function openFolderPicker() {
      const input = document.getElementById('folderInput');
      if (input) input.click();
    }
    function openZipPicker() {
      const input = document.getElementById('zipInput');
      if (input) input.click();
    }
    function handleZipUpload(e) {
      const files = Array.from((e.target && e.target.files) || []);
      if (files.length) processInputFiles(files);
      if (e && e.target) e.target.value = "";
    }
    function handleDrop(e) { dragCounter.value = 0; dragOver.value = false; const files = Array.from((e.dataTransfer && e.dataTransfer.files) || []); if (files.length) processInputFiles(files); }

    async function processInputFiles(files) {
      const zipFiles = files.filter(f => /\.zip$/i.test(f.name || ''));
      const normalFiles = files.filter(f => !/\.zip$/i.test(f.name || ''));
      if (normalFiles.length) processFiles(normalFiles);
      for (const zipFile of zipFiles) {
        await processZipFile(zipFile);
      }
    }

    async function processZipFile(zipFile) {
      if (typeof JSZip === 'undefined') {
        alert('JSZip is not loaded. Please check internet connection or include jszip.min.js locally.');
        return;
      }
      selectedPanel.value = 'system';
      loadedSourceName.value = zipFile.name || 'Dowsing ZIP';
      document.title = `Precog - ${loadedSourceName.value.replace(/\.zip$/i, '').slice(0, 10)}`;
      try {
        const zip = await JSZip.loadAsync(zipFile);
        const entries = Object.values(zip.files).filter(entry => !entry.dir);
        loadedFileNames.value = entries.map(entry => entry.name).sort((a, b) => a.localeCompare(b));
        for (const entry of entries) {
          const lower = entry.name.toLowerCase();
          if (/\.(evtx|exe|dll|png|jpg|jpeg|gif|bin)$/i.test(lower)) continue;
          const text = await entry.async('text');
          parseLoadedFile(entry.name, text);
        }
      } catch (err) {
        console.error('ZIP parse error', err);
        alert('Failed to read ZIP file: ' + (err && err.message ? err.message : err));
      }
    }

    function parseLoadedFile(fileName, text) {
      const fullName = String(fileName || '').replace(/\\/g, '/');
      const name = fullName.split('/').pop().toLowerCase();
      try {
        // Dowsing Debug mode stores raw published INF files under OEM_INF/.
        // Accept the folder explicitly so unrelated .inf files are not mistaken for evidence.
        if (/(^|\/)oem_inf\/oem\d+\.inf$/i.test(fullName)) {
          oemInfContents.value[name] = text || '';
          return;
        }
        if (name.includes('_dism_driverinfo')) parseDism(text);
        else if (name.includes('_pnpparentdevices.csv')) parentDeviceRows.value = parseCsv(text);
        else if (name.includes('_pnpdevicestatus.json')) parsePnpDeviceStatus(text);
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
      } catch (err) { console.error('Parse error in', fileName, err); }
    }

    function processFiles(files) {
      loadedFileNames.value = files.map(f => f.webkitRelativePath || f.name).sort((a, b) => a.localeCompare(b));
      const firstPath = files[0] && (files[0].webkitRelativePath || files[0].name) || '';
      loadedSourceName.value = firstPath.includes('/') ? firstPath.split('/')[0] : (firstPath || 'Selected files');
      document.title = `Precog - ${loadedSourceName.value.slice(0, 10)}`;
      selectedPanel.value = 'system';
      files.forEach(file => {
        const reader = new FileReader();
        reader.onload = evt => {
          parseLoadedFile(file.webkitRelativePath || file.name, evt.target.result);
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
    function parsePnpDeviceStatus(text) {
      try {
        const obj = JSON.parse(text);
        pnpDeviceStatus.value = Array.isArray(obj) ? obj : (obj.Devices || obj.devices || obj.Items || obj.items || []);
      } catch { pnpDeviceStatus.value = []; }
    }
    function parseHardwareInventory(text) { try { hardwareInventory.value = JSON.parse(text); } catch { hardwareInventory.value = {}; } }





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

    function formatBiosReleaseDate(value) {
      if (value == null || value === '') return 'N/A';
      const raw = String(value).trim();
      const microsoftJsonDate = raw.match(/^\/?Date\((-?\d+)(?:[+-]\d{4})?\)\/?$/i);
      let date = null;

      if (microsoftJsonDate) {
        date = new Date(Number(microsoftJsonDate[1]));
      } else if (/^\d{13}$/.test(raw)) {
        date = new Date(Number(raw));
      } else if (/^\d{10}$/.test(raw)) {
        date = new Date(Number(raw) * 1000);
      } else {
        const parsed = new Date(raw);
        if (!Number.isNaN(parsed.getTime())) date = parsed;
      }

      if (!date || Number.isNaN(date.getTime())) return raw;
      const year = date.getUTCFullYear();
      const month = String(date.getUTCMonth() + 1).padStart(2, '0');
      const day = String(date.getUTCDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
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

    function showDeviceOverview() {
      selectedDevice.value = null;
    }

    function clearDeviceFilter() {
      deviceKeyword.value = '';
      nextTick(() => {
        if (deviceFilterInput.value) deviceFilterInput.value.focus();
      });
    }

    function clearDriverFilter() {
      keyword.value = '';
      nextTick(() => {
        if (driverFilterInput.value) driverFilterInput.value.focus();
      });
    }

    function getDeviceCategoryEmoji(className) {
      const key = String(className || '').toLowerCase();
      const map = [
        [/audio|sound|media/, '🔊'],
        [/battery/, '🔋'],
        [/bluetooth/, '🟦'],
        [/camera|image/, '📷'],
        [/display|monitor/, '🖥️'],
        [/keyboard/, '⌨️'],
        [/mouse|pointing|touchpad/, '🖱️'],
        [/network|net/, '🌐'],
        [/processor|cpu/, '💻'],
        [/storage|disk|drive|scsiadapter|volume/, '💾'],
        [/usb|universal serial/, '🔌'],
        [/system/, '⚙️'],
        [/firmware|bios/, '🧩'],
        [/security|tpm/, '🔐'],
        [/sensor/, '📡'],
        [/printer|printqueue/, '🖨️'],
        [/port|com|lpt/, '🔗'],
        [/software/, '📦'],
        [/biometric/, '🧬'],
        [/hidclass/, '🎮'],
        [/unknown/, '❓']
      ];
      const hit = map.find(([pattern]) => pattern.test(key));
      return hit ? hit[1] : '•';
    }

    function isHighlightedDevice(dev) { if (!selectedOem.value) return false; return (dev.activeDriver || '').toLowerCase() === (selectedOem.value.publishedName || '').toLowerCase(); }
    function getDriverObjectByName(name) { if (!name) return null; return dismDrivers.value.find(d => d.publishedName.toLowerCase() === String(name).toLowerCase()) || null; }
    function openDriverFromDevice(dev) { const d = getDriverObjectByName(dev.activeDriver); if (d) { selectedOem.value = d; selectedPanel.value = 'driver'; } }

    function openDeviceFromDriver(dev) {
      if (!dev) return;
      const instanceId = String(dev.instanceId || dev.InstanceId || '').toLowerCase();
      const target = fullDeviceList.value.find(item => String(item.instanceId || item.InstanceId || '').toLowerCase() === instanceId) || {
        name: dev.description || dev.name || 'Unknown Device',
        instanceId: dev.instanceId || dev.InstanceId || '',
        className: dev.deviceClass || dev.Class || 'Unknown',
        activeDriver: selectedOem.value?.publishedName || '',
        status: dev.specificInfStatus || '',
        isProblem: !!getProblemData(dev.instanceId || dev.InstanceId),
        hwids: dev.hwids || []
      };
      selectedDevice.value = target;
      if (target.className) collapsedDeviceClasses.value[target.className] = false;
      deviceManagerView.value = 'devices';
      selectedPanel.value = 'deviceManager';
    }

    function openProblemDevice(record) {
      if (!record) return;
      const instanceId = String(record.pnpId || record.instanceId || record.InstanceId || '').toLowerCase();
      const target = fullDeviceList.value.find(item => String(item.instanceId || item.InstanceId || '').toLowerCase() === instanceId);
      if (target) {
        selectedDevice.value = target;
        if (target.className) collapsedDeviceClasses.value[target.className] = false;
      } else {
        selectedDevice.value = {
          name: record.name || record.description || record.FriendlyName || 'Unknown Device',
          instanceId: record.pnpId || record.instanceId || record.InstanceId || '',
          className: record.Class || record.className || 'Unknown',
          status: record.Status || '',
          isProblem: true,
          isGhost: isGhostProblemRecord(record),
          activeDriver: '',
          hwids: []
        };
      }
      deviceManagerView.value = 'devices';
      selectedPanel.value = 'deviceManager';
    }

    return { dragOver, loadedFileNames, loadedSourceName, selectedPanel, deviceManagerView, keyword, driverFilterInput, clearDriverFilter, filterProvider, filterStatus, selectedOem, selectedDevice, deviceKeyword, deviceFilterInput, clearDeviceFilter, deviceOnlyProblem, deviceOnlyHighlighted, selectedProblemTab, collapsedDeviceClasses, dismDrivers, pnpDevices, pnpCsvDevices, problemDevices, pnpProblemDevices, pnpProblemCsvDevices, catalogMap, sysInfo, systemSummary, collectionStatus, runLogText, rawWindowsVersionReg, winRegParsed, statusOptions, hasData, providers, systemHeadline, windowsReleaseLabel, secureBootClass, problemDevicesCombined, ghostDevices, summaryCards, collectionOkCount, collectionMissingCount, systemHealthLoadedCount, systemInfoGeneratedTime, hardwareSummaryRows, finalFilteredDrivers, matchedPnpDevices, fullDeviceList, filteredDeviceGroups, disabledDevices, platformHealthCards, powerRequestStatus, healthStatusClass, rawDxDiagText, rawPowerCfgA, rawPowerCfgRequests, rawPowerCfgLastWake, rawPowerCfgWakeArmed, rawSleepStudyText, rawEnergyReportText, displayAudioCameraRows, usbTypecRows, vendorRows, hardwareInventory, platformConfigurationSections, platformConfigurationHeadline, resetTool, handleBatchUpload, handleZipUpload, handleDrop, checkOemStatus, statusLabel, badgeClass, getProblemData, getSignerSummary, isNonWhql, collectionBadgeClass, driverStatusClass, getCatalogFileName, jsonFilter, regFilter, filteredSystemSummary, filteredWinReg, onDragEnter, onDragOver, onDragLeave, analyzeDriver, showDecodedReg, formatRegValue, formatBiosReleaseDate, getDeviceHuntInfo, navClass, isHighlightedDevice, getDriverObjectByName, openDriverFromDevice, openDeviceFromDriver, openProblemDevice, showDeviceOverview, getDeviceCategoryEmoji, isGhostProblemRecord, isDeviceClassCollapsed, toggleDeviceClass, openFolderPicker, openZipPicker, installedAppsWin32, installedAppsAppx, provisionedApps, startupApps, installedUpdates, servicesRows, scheduledTasksRows, showMicrosoftApps, appFilterKeyword, appFilterInput, appPublisherFilter, appAudienceFilter, startupAppsExpanded, appPublisherOptions, setAppAudience, clearAppFilter, allCombinedInstalledApps, combinedInstalledApps, allStartupApps, filteredStartupApps, appsOverviewCards, rawDefaultAppsText, rawPowerPlanText, rawIPConfigText, rawPnpInterfacesText, rawScheduledTasksText, pnpDeviceStatus, parentDeviceRows, expandedConnectionNodes,
      connectionTopology, connectionTreeRows, connectionFilterActive,
      isConnectionExpanded, toggleConnectionNode, selectConnectionDevice, getParentConnection,
      activeSystemSection, getDeviceStatus, scrollSystemSection, operationsLogCards,
      oemInfContents, infViewerOpen, infViewerName, infViewerContent, infViewerSearch,
      infViewerCopyLabel, infViewerRenderedContent, infViewerMatchCount,
      hasOriginalInfContent, openInfViewer, closeInfViewer, copyInfContent };
  }
}).mount('#app');
