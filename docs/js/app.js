(function () {
    'use strict';

    // Month names in Spanish
    var MONTHS = [
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'
    ];

    // Short month names for compact display
    var MONTHS_SHORT = [
        'ene', 'feb', 'mar', 'abr', 'may', 'jun',
        'jul', 'ago', 'sep', 'oct', 'nov', 'dic'
    ];

    var data = null;
    var counterInterval = null;

    // DOM element references
    var elDays = document.getElementById('days');
    var elHours = document.getElementById('hours');
    var elMinutes = document.getElementById('minutes');
    var elLastAccident = document.getElementById('last-accident');
    var elErrorMsg = document.getElementById('error-msg');
    var elBtnRetry = document.getElementById('btn-retry');
    var elCounter = document.getElementById('counter');
    var elStaleWarning = document.getElementById('stale-warning');
    var elHistoryList = document.getElementById('history-list');
    var elStatTotal = document.getElementById('stat-total');
    var elStatStreak = document.getElementById('stat-streak');
    var elSourcesList = document.getElementById('sources-list');

    /**
     * Format a date as "11 de marzo de 2026, 14:30"
     */
    function formatDate(date) {
        var d = new Date(date);
        var day = d.getDate();
        var month = MONTHS[d.getMonth()];
        var year = d.getFullYear();
        var hours = String(d.getHours()).padStart(2, '0');
        var minutes = String(d.getMinutes()).padStart(2, '0');
        return day + ' de ' + month + ' de ' + year + ', ' + hours + ':' + minutes;
    }

    /**
     * Format a date as "11 mar 2026"
     */
    function formatShortDate(date) {
        var d = new Date(date);
        var day = d.getDate();
        var month = MONTHS_SHORT[d.getMonth()];
        var year = d.getFullYear();
        return day + ' ' + month + ' ' + year;
    }

    /**
     * Hide the counter section and show the error message.
     * Attach retry listener.
     */
    function showError() {
        elDays.textContent = '—';
        elHours.textContent = '—';
        elMinutes.textContent = '—';
        elLastAccident.textContent = '';
        elErrorMsg.classList.remove('hidden');

        elBtnRetry.addEventListener('click', function () {
            window.location.reload();
        });
    }

    /**
     * Update the counter display every second.
     */
    function updateCounter() {
        var now = new Date();
        var last = new Date(data.ultimo_accidente);
        var diffMs = now - last;

        if (diffMs < 0) {
            diffMs = 0;
        }

        var totalMinutes = Math.floor(diffMs / 60000);
        var totalHours = Math.floor(totalMinutes / 60);
        var days = Math.floor(totalHours / 24);
        var hours = totalHours % 24;
        var minutes = totalMinutes % 60;

        elDays.textContent = String(days);
        elHours.textContent = String(hours);
        elMinutes.textContent = String(minutes);
    }

    /**
     * If the last pipeline run was more than 48 hours ago, show warning.
     */
    function checkStale() {
        if (!data.ultima_ejecucion) {
            return;
        }
        var lastRun = new Date(data.ultima_ejecucion);
        var now = new Date();
        var diffHours = (now - lastRun) / (1000 * 60 * 60);
        if (diffHours > 48) {
            elStaleWarning.classList.remove('hidden');
        }
    }

    /**
     * Render the history list from the accidents array.
     * Uses safe DOM methods only — no innerHTML.
     */
    function renderHistory(accidents) {
        // Clear existing content
        while (elHistoryList.firstChild) {
            elHistoryList.removeChild(elHistoryList.firstChild);
        }

        // Show up to the first 10
        var items = accidents.slice(0, 10);

        items.forEach(function (accident) {
            var item = document.createElement('div');
            item.className = 'history-item';

            var dateSpan = document.createElement('span');
            dateSpan.className = 'history-date';
            dateSpan.textContent = formatShortDate(accident.fecha);

            var content = document.createElement('div');
            content.className = 'history-content';

            var titleLink = document.createElement('a');
            titleLink.className = 'history-title';
            titleLink.textContent = accident.titulo;
            if (accident.url) {
                titleLink.href = accident.url;
                titleLink.target = '_blank';
                titleLink.rel = 'noopener noreferrer';
            }

            var sourceDiv = document.createElement('div');
            sourceDiv.className = 'history-source';
            sourceDiv.textContent = accident.fuente || '';

            content.appendChild(titleLink);
            content.appendChild(sourceDiv);

            item.appendChild(dateSpan);
            item.appendChild(content);

            elHistoryList.appendChild(item);
        });
    }

    /**
     * Render stat cards.
     */
    function renderStats() {
        elStatTotal.textContent = String(data.total_accidentes);
        elStatStreak.textContent = String(data.racha_maxima_dias);
    }

    /**
     * Render a bar chart of accidents per month for the last 12 months.
     */
    function renderMonthlyChart() {
        var canvas = document.getElementById('monthly-chart');
        if (!canvas) {
            return;
        }

        // Build last 12 months labels and counts
        var now = new Date();
        var labels = [];
        var counts = [];
        var monthKeys = [];

        for (var i = 11; i >= 0; i--) {
            var d = new Date(now.getFullYear(), now.getMonth() - i, 1);
            var key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
            monthKeys.push(key);
            labels.push(MONTHS_SHORT[d.getMonth()] + ' ' + d.getFullYear());
            counts.push(0);
        }

        // Count accidents per month
        if (data.accidentes && data.accidentes.length > 0) {
            data.accidentes.forEach(function (accident) {
                var ad = new Date(accident.fecha);
                var aKey = ad.getFullYear() + '-' + String(ad.getMonth() + 1).padStart(2, '0');
                var idx = monthKeys.indexOf(aKey);
                if (idx !== -1) {
                    counts[idx]++;
                }
            });
        }

        // Create chart
        new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Accidentes',
                    data: counts,
                    backgroundColor: 'rgba(231, 76, 60, 0.7)',
                    borderColor: '#e74c3c',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#888',
                            font: {
                                family: "'Courier New', 'Consolas', monospace",
                                size: 10
                            }
                        },
                        grid: {
                            color: '#333'
                        }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#888',
                            stepSize: 1,
                            font: {
                                family: "'Courier New', 'Consolas', monospace",
                                size: 10
                            }
                        },
                        grid: {
                            color: '#333'
                        }
                    }
                }
            }
        });
    }

    /**
     * Render the list of consulted sources.
     */
    function renderSources(sources) {
        while (elSourcesList.firstChild) {
            elSourcesList.removeChild(elSourcesList.firstChild);
        }

        sources.forEach(function (source) {
            var li = document.createElement('li');
            li.textContent = source;
            elSourcesList.appendChild(li);
        });
    }

    /**
     * Main render function called after data loads successfully.
     */
    function render() {
        if (!data.ultimo_accidente) {
            elDays.textContent = '—';
            elHours.textContent = '—';
            elMinutes.textContent = '—';
            elLastAccident.textContent = 'Sin datos registrados aún.';
        } else {
            // Start the live counter
            updateCounter();
            counterInterval = setInterval(updateCounter, 1000);

            // Show the last accident date
            elLastAccident.textContent = 'Último accidente: ' + formatDate(data.ultimo_accidente);
        }

        // Check for stale data
        checkStale();

        // Render sections
        renderHistory(data.accidentes || []);
        renderStats();
        renderMonthlyChart();
        renderSources(data.fuentes_consultadas || []);
    }

    /**
     * Initialize: fetch data and render or show error.
     */
    function init() {
        fetch('data/accidentes.json')
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return response.json();
            })
            .then(function (json) {
                data = json;
                render();
            })
            .catch(function () {
                showError();
            });
    }

    init();
})();
