(function () {
  var section = document.getElementById("sellerTrustSection");
  if (!section) return;

  function getCookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function csrfToken() {
    return getCookie("csrftoken");
  }

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      body: JSON.stringify(payload),
    }).then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, data: data };
      });
    });
  }

  var reviewsUrl = section.getAttribute("data-reviews-url");
  var reviewCreateUrl = section.getAttribute("data-review-create-url");
  var reportCreateUrl = section.getAttribute("data-report-create-url");
  var equipmentIdRaw = (section.getAttribute("data-equipment-id") || "").trim();
  var equipmentId = equipmentIdRaw ? parseInt(equipmentIdRaw, 10) : null;
  var sellerId = parseInt(section.getAttribute("data-seller-id"), 10);

  var currentReviewType = "all";
  var currentReviewPage = 1;
  var reviewsLoading = false;

  var listEl = document.getElementById("trustReviewsList");
  var moreBtn = document.getElementById("trustReviewsMore");

  function renderReviews(items, append) {
    if (!listEl) return;
    if (!items || !items.length) {
      if (!append) {
        listEl.innerHTML = '<p class="text-muted mb-0">' + (window.TRUST_I18N_EMPTY || "아직 후기가 없습니다.") + "</p>";
      }
      return;
    }
    var html = items
      .map(function (r) {
        var badge =
          r.review_type === "good"
            ? '<span class="badge bg-success">+</span>'
            : '<span class="badge bg-secondary">-</span>';
        var comment = r.comment
          ? '<div class="text-muted mt-1">' + escapeHtml(r.comment) + "</div>"
          : "";
        return (
          '<div class="border-bottom py-2">' +
          badge +
          ' <span class="fw-semibold">' +
          escapeHtml(r.reviewer_name || "") +
          "</span>" +
          comment +
          "</div>"
        );
      })
      .join("");
    if (append) listEl.insertAdjacentHTML("beforeend", html);
    else listEl.innerHTML = html;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function loadReviews(page, append) {
    if (reviewsLoading || !reviewsUrl) return;
    reviewsLoading = true;
    var url =
      reviewsUrl +
      "?page=" +
      page +
      (currentReviewType !== "all" ? "&type=" + currentReviewType : "");
    fetch(url, { credentials: "same-origin" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data.ok) return;
        renderReviews(data.reviews, append);
        currentReviewPage = data.page;
        if (moreBtn) {
          if (data.page < data.num_pages) moreBtn.classList.remove("d-none");
          else moreBtn.classList.add("d-none");
        }
      })
      .finally(function () {
        reviewsLoading = false;
      });
  }

  document.querySelectorAll(".gn-trust-review-tabs .nav-link").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".gn-trust-review-tabs .nav-link").forEach(function (b) {
        b.classList.remove("active");
      });
      btn.classList.add("active");
      currentReviewType = btn.getAttribute("data-review-type") || "all";
      currentReviewPage = 1;
      loadReviews(1, false);
    });
  });

  if (moreBtn) {
    moreBtn.addEventListener("click", function () {
      loadReviews(currentReviewPage + 1, true);
    });
  }

  loadReviews(1, false);

  /* 평가 모달 */
  var reviewModal = document.getElementById("trustReviewModal");
  var badWrap = document.getElementById("trustBadTagsWrap");
  var scoreSelections = {};

  document.querySelectorAll(".trust-score-btns").forEach(function (group) {
    var field = group.getAttribute("data-score-field");
    group.querySelectorAll("button[data-score]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        group.querySelectorAll("button").forEach(function (b) {
          b.classList.remove("btn-primary", "active");
          b.classList.add("btn-outline-secondary");
        });
        btn.classList.remove("btn-outline-secondary");
        btn.classList.add("btn-primary", "active");
        scoreSelections[field] = parseInt(btn.getAttribute("data-score"), 10);
      });
    });
  });

  document.querySelectorAll('input[name="trustReviewType"]').forEach(function (radio) {
    radio.addEventListener("change", function () {
      var isBad = document.querySelector('input[name="trustReviewType"]:checked').value === "bad";
      if (badWrap) badWrap.classList.toggle("d-none", !isBad);
      document.querySelectorAll("#trustReviewTypeGroup label").forEach(function (lbl) {
        lbl.classList.remove("active");
      });
      if (radio.parentElement) radio.parentElement.classList.add("active");
    });
  });

  var reviewSubmit = document.getElementById("trustReviewSubmit");
  var reviewError = document.getElementById("trustReviewError");

  if (reviewSubmit) {
    reviewSubmit.addEventListener("click", function () {
      var reviewType = document.querySelector('input[name="trustReviewType"]:checked').value;
      var payload = {
        review_type: reviewType,
        comment: (document.getElementById("trustReviewComment") || {}).value || "",
        bad_tags: [],
      };
      if (equipmentId) payload.equipment_id = equipmentId;
      Object.keys(scoreSelections).forEach(function (k) {
        payload[k] = scoreSelections[k];
      });
      if (reviewType === "bad") {
        document.querySelectorAll(".trust-bad-tag").forEach(function (cb) {
          if (cb.checked) payload.bad_tags.push(cb.value);
        });
      }
      postJson(reviewCreateUrl, payload).then(function (res) {
        if (res.ok && res.data.ok) {
          if (reviewModal && window.bootstrap) {
            bootstrap.Modal.getInstance(reviewModal).hide();
          }
          location.reload();
          return;
        }
        if (reviewError) {
          reviewError.textContent = (res.data && res.data.error) || "오류가 발생했습니다.";
          reviewError.classList.remove("d-none");
        }
      });
    });
  }

  document.querySelectorAll("#trustBadTagsGroup label").forEach(function (lbl) {
    lbl.addEventListener("click", function () {
      var cb = lbl.querySelector(".trust-bad-tag");
      if (!cb) return;
      setTimeout(function () {
        lbl.classList.toggle("active", cb.checked);
      }, 0);
    });
  });

  /* 신고 */
  var reportSubmit = document.getElementById("trustReportSubmit");
  var reportError = document.getElementById("trustReportError");
  var reportModal = document.getElementById("trustReportModal");

  if (reportSubmit) {
    reportSubmit.addEventListener("click", function () {
      var reasonEl = document.getElementById("trustReportReason");
      postJson(reportCreateUrl, {
        seller_id: sellerId,
        equipment_id: equipmentId,
        reason: reasonEl ? reasonEl.value : "",
        detail: (document.getElementById("trustReportDetail") || {}).value || "",
      }).then(function (res) {
        if (res.ok && res.data.ok) {
          if (reportModal && window.bootstrap) {
            bootstrap.Modal.getInstance(reportModal).hide();
          }
          alert(res.data.message || "신고가 접수되었습니다.");
          return;
        }
        if (reportError) {
          reportError.textContent = (res.data && res.data.error) || "오류가 발생했습니다.";
          reportError.classList.remove("d-none");
        }
      });
    });
  }
})();
