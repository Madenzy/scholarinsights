// Animated bar chart
(function () {
  const chart = document.getElementById("chart");
  if (!chart) return;
  const heights = [55, 72, 48, 80, 65, 90, 76, 82, 68, 95, 88, 74];
  heights.forEach((h, i) => {
    const bar = document.createElement("div");
    bar.className = "chart__bar";
    bar.style.height = "0%";
    chart.appendChild(bar);
    setTimeout(() => { bar.style.height = h + "%"; }, 80 * i + 150);
  });
})();

// Smooth scroll for in-page anchors
document.querySelectorAll('a[href^="#"]').forEach((a) => {
  a.addEventListener("click", (e) => {
    const id = a.getAttribute("href");
    if (!id || id === "#") return;
    const el = document.querySelector(id);
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
});

// Animate stats count-up
(function () {
  const nums = document.querySelectorAll(".stats dt");
  const animate = (el) => {
    const raw = el.textContent.trim();
    const isPct = raw.endsWith("%");
    const target = parseFloat(raw.replace(/[^\d.]/g, ""));
    if (isNaN(target)) return;
    const duration = 1200;
    const start = performance.now();
    const fmt = (n) => isPct ? Math.round(n) + "%" : Math.round(n).toLocaleString();
    const step = (now) => {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(target * eased);
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { animate(e.target); io.unobserve(e.target); }
    });
  }, { threshold: 0.4 });
  nums.forEach((n) => io.observe(n));
})();

// Contact form
(function () {
  // Set this to your deployed endpoint. The form posts JSON to API_URL.
  const API_URL = "https://project--2b284714-ce74-4073-b3cf-6fb24bd4a1f2.lovable.app/api/public/contact";

  const form = document.getElementById("contactForm");
  if (!form) return;
  const btn = document.getElementById("cfSubmit");
  const status = document.getElementById("cfStatus");

  const setError = (name, msg) => {
    const field = form.querySelector(`[name="${name}"]`)?.closest(".field");
    const errEl = form.querySelector(`[data-error-for="${name}"]`);
    if (field) field.classList.toggle("is-invalid", !!msg);
    if (errEl) errEl.textContent = msg || "";
  };

  const clearErrors = () => {
    ["name", "email", "school", "message"].forEach((n) => setError(n, ""));
  };

  const validate = (data) => {
    const errors = {};
    if (!data.name || data.name.length < 1) errors.name = "Please enter your name";
    else if (data.name.length > 100) errors.name = "Name is too long";
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email);
    if (!data.email) errors.email = "Email is required";
    else if (!emailOk) errors.email = "Please enter a valid email";
    if (data.school && data.school.length > 150) errors.school = "Too long";
    if (!data.message) errors.message = "Message can't be empty";
    else if (data.message.length > 2000) errors.message = "Message is too long";
    return errors;
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearErrors();
    status.textContent = "";
    status.classList.remove("is-success", "is-error");

    const fd = new FormData(form);
    const data = {
      name: (fd.get("name") || "").toString().trim(),
      email: (fd.get("email") || "").toString().trim(),
      school: (fd.get("school") || "").toString().trim(),
      message: (fd.get("message") || "").toString().trim(),
    };

    const errors = validate(data);
    if (Object.keys(errors).length) {
      Object.entries(errors).forEach(([k, v]) => setError(k, v));
      return;
    }

    btn.classList.add("is-loading");
    btn.disabled = true;

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      const json = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (json && json.issues) {
          Object.entries(json.issues).forEach(([k, arr]) => {
            if (Array.isArray(arr) && arr[0]) setError(k, String(arr[0]));
          });
        }
        throw new Error(json.error || `Request failed (${res.status})`);
      }

      status.textContent = json.message || "Thanks! We'll be in touch shortly.";
      status.classList.add("is-success");
      form.reset();
    } catch (err) {
      status.textContent = err.message || "Something went wrong. Please try again.";
      status.classList.add("is-error");
    } finally {
      btn.classList.remove("is-loading");
      btn.disabled = false;
    }
  });
})();