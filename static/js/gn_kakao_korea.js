/**
 * 카카오맵을 대한민국 영역으로 제한하는 공통 유틸.
 * - /parts-as/ 메인 지도와 장비 상세 사이드바 "전국 부품점 A/S센터" 위젯에서 공통 사용.
 * - 카카오맵은 기본 restriction 옵션이 없어 이벤트로 직접 범위를 제한한다.
 */
(function (global) {
  "use strict";

  // 대한민국 영역 (남서쪽 SW ~ 북동쪽 NE)
  var KOREA_SW = { lat: 33.0, lng: 124.5 };
  var KOREA_NE = { lat: 38.7, lng: 132.0 };

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  /**
   * 지도를 대한민국 영역 안으로 제한한다.
   * @param {kakao.maps.Map} map
   * @param {Object} [options]
   * @param {number} [options.maxLevel] 줌아웃(축소) 한계 레벨. 카카오는 레벨이 클수록 축소되므로
   *   이 값으로 "가장 축소된 상태"를 제한한다(=한국 전체가 화면을 채우는 수준).
   * @param {number} [options.minLevel] 확대 한계 레벨(선택).
   * @returns {kakao.maps.LatLngBounds|undefined} 한국 영역 bounds
   */
  function restrictMapToKorea(map, options) {
    if (!map || typeof kakao === "undefined" || !kakao.maps) return undefined;
    options = options || {};

    if (typeof options.maxLevel === "number") {
      map.setMaxLevel(options.maxLevel);
    }
    if (typeof options.minLevel === "number") {
      map.setMinLevel(options.minLevel);
    }

    var boundLimit = new kakao.maps.LatLngBounds(
      new kakao.maps.LatLng(KOREA_SW.lat, KOREA_SW.lng),
      new kakao.maps.LatLng(KOREA_NE.lat, KOREA_NE.lng)
    );

    // 현재 지도 중심이 한국 영역을 벗어나면 가장 가까운 한국 영역 내 좌표로 되돌린다.
    function keepInKorea() {
      var center = map.getCenter();
      var lat = center.getLat();
      var lng = center.getLng();
      var clampedLat = clamp(lat, KOREA_SW.lat, KOREA_NE.lat);
      var clampedLng = clamp(lng, KOREA_SW.lng, KOREA_NE.lng);
      if (clampedLat !== lat || clampedLng !== lng) {
        map.panTo(new kakao.maps.LatLng(clampedLat, clampedLng));
      }
    }

    kakao.maps.event.addListener(map, "dragend", keepInKorea);
    kakao.maps.event.addListener(map, "zoom_changed", keepInKorea);

    return boundLimit;
  }

  global.GNKakaoKorea = {
    restrictMapToKorea: restrictMapToKorea,
    KOREA_SW: KOREA_SW,
    KOREA_NE: KOREA_NE,
  };
})(window);
