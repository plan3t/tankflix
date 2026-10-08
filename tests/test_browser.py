import base64
import os
import re
import shutil
import unittest

from playwright.sync_api import sync_playwright, expect

from tests.support import AppServer, UNSAFE_NAME


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = AppServer()
        cls.playwright = sync_playwright().start()
        executable = os.getenv('TANKFLIX_BROWSER_EXECUTABLE') or shutil.which('chromium') or shutil.which('google-chrome')
        cls.browser = cls.playwright.chromium.launch(headless=True, executable_path=executable, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 960}, reduced_motion='reduce')
        # Only the optional basemap is mocked; Leaflet itself and the app use real local assets.
        self.context.route('https://*.tile.openstreetmap.org/**', lambda route: route.fulfill(
            status=200, content_type='image/png', body=base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')))
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [], f'Browser JS errors: {self.errors}')

    def open(self, fuel='e5'):
        self.page.goto(self.server.url + '/?fuel=' + fuel)
        expect(self.page.locator('#result-count')).to_contain_text('5 von 5')

    def row(self, identity):
        return self.page.locator(f'[data-station-row][data-id="{identity}"]')

    def visible_ids(self):
        return self.page.locator('[data-station-row]:visible').evaluate_all('(rows) => rows.map(row => row.dataset.id)')

    def test_table_to_map_cheapest_ties_popup_and_reverse_selection(self):
        self.open()
        expect(self.row('near').locator('.best-badge')).to_be_visible()
        expect(self.row('tie').locator('.best-badge')).to_be_visible()
        self.row('near').get_by_role('button', name='Auf Karte zeigen').click()
        expect(self.page.locator('.price-marker.is-selected')).to_contain_text('1,700')
        expect(self.page.locator('.leaflet-popup')).to_contain_text('Alpha Zentrum')
        expect(self.row('near')).to_have_class(re.compile('selected-station'))
        self.page.locator('.leaflet-popup-close-button').click()
        self.page.get_by_role('button', name='Alpha Nord, 1,700 €/L, Günstigste', exact=True).click()
        expect(self.row('tie')).to_have_class(re.compile('selected-station'))
        self.page.locator('.leaflet-popup').get_by_role('button', name='Zur Liste', exact=True).click()
        self.assertEqual(self.page.evaluate('document.activeElement.dataset.id'), 'tie')
        self.page.locator('#show-cheapest').click()
        expect(self.page.locator('#selection-status')).to_contain_text('Alpha Zentrum')
        expect(self.page.locator('.leaflet-popup a.btn-link')).to_have_attribute('href', re.compile('destination=51.99%2C8.61'))

    def test_search_sort_filters_map_and_empty_state_stay_consistent(self):
        self.open()
        self.page.locator('#sort-order').select_option('distance')
        self.assertEqual(self.visible_ids()[0], 'closed')
        self.page.locator('#station-search').fill('teststraße')
        self.page.locator('#brand-filter').select_option('Alpha')
        self.page.locator('#distance-filter').fill('2.5')
        self.page.locator('#open-only').check()
        self.assertEqual(self.visible_ids(), ['near', 'tie'])
        expect(self.page.locator('#result-count')).to_contain_text('2 von 5')
        expect(self.page.locator('.leaflet-marker-icon[title*="Beta Express"]')).to_have_count(0)
        self.page.locator('#station-search').fill('does-not-exist')
        expect(self.page.locator('#filter-empty')).to_be_visible()
        expect(self.page.locator('#show-cheapest')).to_be_disabled()
        expect(self.page.locator('.price-marker, .cluster-label')).to_have_count(0)
        self.page.locator('#reset-filters').click()
        self.assertEqual(len(self.visible_ids()), 5)
        self.page.locator('#brand-filter').select_option('Beta')
        expect(self.row('closed').locator('.best-badge')).to_be_visible()
        expect(self.row('near')).to_be_hidden()

    def test_favorites_comparison_sort_and_fuel_selection_persistence(self):
        self.open()
        self.row('near').locator('.fav-btn').click()
        self.row('old').locator('.fav-btn').click()
        expect(self.page.locator('#favorite-summary')).to_contain_text('2 sichtbare')
        expect(self.page.locator('#favorite-comparison')).to_contain_text('Günstigster Favorit')
        self.page.locator('#sort-order').select_option('favorites')
        self.assertEqual(self.visible_ids()[:2], ['near', 'old'])
        self.page.locator('#show-favorite').click()
        expect(self.page.locator('#selection-status')).to_contain_text('Alpha Zentrum')
        self.page.get_by_role('link', name='Diesel', exact=True).click()
        expect(self.page.locator('#selection-status')).to_contain_text('Alpha Zentrum · 1,600')
        expect(self.row('tie').locator('.best-badge')).to_be_visible()
        expect(self.row('near').locator('.best-badge')).to_be_hidden()
        expect(self.row('near').locator('.fav-btn')).to_have_attribute('aria-pressed', 'true')
        self.page.locator('#favorites-only').check()
        self.assertEqual(self.visible_ids(), ['near', 'old'])
        self.page.reload()
        expect(self.page.locator('#favorites-only')).to_be_checked()
        expect(self.row('near').locator('.fav-btn')).to_have_attribute('aria-pressed', 'true')

    def test_details_history_ranges_alert_explanation_and_retry(self):
        self.open()
        self.row('near').get_by_role('button', name='Details & Verlauf').click()
        expect(self.page.locator('#station-details')).to_be_visible()
        expect(self.page.locator('#detail-alerts')).to_contain_text('Preisgrenze: 1,800')
        expect(self.page.locator('#detail-alerts')).to_contain_text('-20 Cent')
        expect(self.page.locator('#history-status')).to_contain_text('3 Messwerte')
        expect(self.page.locator('#history-chart')).to_be_visible()
        self.page.locator('#history-period').select_option('30')
        expect(self.page.locator('#history-status')).to_contain_text('4 Messwerte')
        self.page.locator('#history-period').select_option('1')
        expect(self.page.locator('#history-status')).to_contain_text('2 Messwerte')
        self.page.route('**/api/stations/**', lambda route: route.fulfill(status=503, body='unavailable'))
        self.page.locator('#history-period').select_option('7')
        expect(self.page.locator('#history-status')).to_contain_text('konnte nicht geladen')
        expect(self.page.locator('#detail-price')).to_contain_text('1,700')
        self.page.unroute('**/api/stations/**')
        self.page.get_by_role('button', name='Erneut laden', exact=True).click()
        expect(self.page.locator('#history-status')).to_contain_text('3 Messwerte')
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#station-details')).to_be_hidden()

    def test_mobile_cards_collapsible_map_keyboard_selection_and_dark_theme(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.open()
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
        self.assertEqual(self.row('near').evaluate("el => getComputedStyle(el).display"), 'grid')
        self.page.locator('#map-panel summary').click()
        expect(self.page.locator('#station-map')).to_be_hidden()
        button = self.row('near').get_by_role('button', name='Auf Karte zeigen')
        button.focus()
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#station-map')).to_be_visible()
        expect(self.page.locator('.price-marker.is-selected')).to_be_visible()
        self.page.locator('#theme-toggle').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'dark')
        self.page.get_by_role('link', name='Admin', exact=True).click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'dark')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)

    def test_map_failure_does_not_break_list_or_favorites(self):
        self.page.route('**/vendor/leaflet/leaflet.js', lambda route: route.abort())
        self.open()
        expect(self.page.locator('#map-error')).to_be_visible()
        expect(self.row('near').get_by_role('button', name='Auf Karte zeigen')).to_be_disabled()
        self.page.locator('#station-search').fill('Alpha Zentrum')
        self.assertEqual(self.visible_ids(), ['near'])
        self.row('near').locator('.fav-btn').click()
        expect(self.page.locator('#favorite-comparison')).to_contain_text('Alpha Zentrum')
        expect(self.row('near').get_by_role('link', name=re.compile('Route zu'))).to_be_visible()

    def test_storage_corruption_untrusted_names_and_stale_badges(self):
        self.page.add_init_script("localStorage.setItem('tankflix-favorites', '{broken'); sessionStorage.setItem('tankflix-view', '{broken');")
        self.open()
        expect(self.row('old').locator('.stale-badge')).to_be_visible()
        self.page.locator('#station-search').fill('ACME')
        self.row('unsafe').get_by_role('button', name='Auf Karte zeigen').click()
        expect(self.page.locator('.leaflet-popup')).to_contain_text(UNSAFE_NAME)
        self.assertIsNone(self.page.evaluate('window.stationXss'))
        expect(self.page.locator('.leaflet-popup img')).to_have_count(0)

    def test_selected_station_survives_filtering_without_leaking_onto_map(self):
        self.open()
        self.row('near').get_by_role('button', name='Auf Karte zeigen').click()
        self.page.locator('#brand-filter').select_option('Beta')
        expect(self.page.locator('#selection-status')).to_contain_text('durch Filter ausgeblendet')
        expect(self.page.locator('.price-marker.is-selected')).to_have_count(0)
        self.page.locator('#reset-filters').click()
        expect(self.page.locator('.price-marker.is-selected')).to_have_count(1)

    def test_cluster_and_station_markers_work_with_keyboard(self):
        self.open()
        expect(self.page.locator('.cluster-label').first).to_be_visible()
        cluster = self.page.locator('.cluster-icon').first
        cluster.focus()
        self.page.keyboard.press('Enter')
        marker = self.page.get_by_role('button', name='Alpha Zentrum, 1,700 €/L, Günstigste', exact=True)
        marker.focus()
        self.page.keyboard.press('Enter')
        expect(self.row('near').locator('.selection-badge')).to_be_visible()
        expect(self.page.locator('.leaflet-popup')).to_contain_text('Alpha Zentrum')

    def test_empty_and_single_point_history_have_clear_accessible_states(self):
        self.page.route('**/api/stations/**', lambda route: route.fulfill(json={'points': []}))
        self.open()
        self.row('near').get_by_role('button', name='Details & Verlauf').click()
        expect(self.page.locator('#history-status')).to_contain_text('noch keine Messwerte')
        expect(self.page.locator('#history-chart')).to_be_hidden()
        self.page.unroute('**/api/stations/**')
        self.page.route('**/api/stations/**', lambda route: route.fulfill(json={
            'points': [{'at': self.server.now.isoformat() + 'Z', 'price': 1.7}]}))
        self.page.locator('#history-period').select_option('1')
        expect(self.page.locator('#history-status')).to_contain_text('noch keinen Trend')
        expect(self.page.locator('#history-chart circle')).to_be_visible()

    def test_disabled_storage_and_unavailable_basemap_remain_usable(self):
        self.page.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw new Error('disabled')}}); Object.defineProperty(window, 'sessionStorage', {get() {throw new Error('disabled')}});")
        self.context.unroute('https://*.tile.openstreetmap.org/**')
        self.context.route('https://*.tile.openstreetmap.org/**', lambda route: route.abort())
        self.open()
        expect(self.page.locator('#map-error')).to_contain_text('Kartenhintergrund')
        self.row('near').locator('.fav-btn').click()
        expect(self.page.locator('#favorite-comparison')).to_contain_text('Alpha Zentrum')
        self.row('near').get_by_role('button', name='Auf Karte zeigen').click()
        expect(self.page.locator('.price-marker.is-selected')).to_be_visible()
        self.page.locator('#theme-toggle').click()
        expect(self.page.locator('html')).to_have_attribute('data-theme', 'dark')
