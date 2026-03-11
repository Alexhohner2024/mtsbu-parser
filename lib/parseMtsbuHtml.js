import cheerio from "cheerio";

const normalizeText = (text) =>
  (text || "")
    .replace(/\s+/g, " ")
    .replace(/\u00a0/g, " ")
    .trim();

const textOf = (el) => normalizeText(el.text());

export function parseMtsbuHtml(html) {
  const $ = cheerio.load(html);

  // --- Заголовок: полис + статус + дата ---
  let policyNumber = null;
  let status = null;
  let statusDate = null;

  const titleBlock = $(".content .title").first();
  if (titleBlock.length) {
    const titleText = textOf(titleBlock);
    const match = titleText.match(/Поліс №\s*([0-9]+)/i);
    if (match) {
      policyNumber = match[1];
    }

    const statusLabel = titleBlock.find(".label").first();
    if (statusLabel.length) {
      status = textOf(statusLabel);
    }
  }

  const dateEl = $(".content .date").first();
  if (dateEl.length) {
    const dateText = textOf(dateEl);
    statusDate = dateText.replace(/^на\s*/i, "").trim();
  }

  // --- Страхова компанія ---
  let companyName = null;
  let companyStatus = null;
  let edrpou = null;
  let address = null;
  let email = null;
  let phone = null;

  const companyHeader = $(".content h3")
    .filter((_, el) => textOf($(el)).includes("Страхова компанія"))
    .first();

  if (companyHeader.length) {
    const section = companyHeader.parent();

    const valueByLabel = (label) => {
      const headline = section
        .find(".headline")
        .filter((_, el) => textOf($(el)) === label)
        .first();
      if (!headline.length) return null;
      const value = headline.next(".value").first();
      if (!value.length) return null;
      return textOf(value);
    };

    companyName = valueByLabel("Найменування");
    companyStatus = valueByLabel("Статус страховика");
    edrpou = valueByLabel("ЄДРПОУ");

    const addrHeadline = section
      .find(".headline")
      .filter((_, el) =>
        textOf($(el)).startsWith("Місцезнаходження, поштова адреса")
      )
      .first();
    if (addrHeadline.length) {
      const v = addrHeadline.next(".value").first();
      if (v.length) address = textOf(v);
    }

    const emailHeadline = section
      .find(".headline")
      .filter((_, el) =>
        textOf($(el)).startsWith("Електронна пошта для звернень")
      )
      .first();
    if (emailHeadline.length) {
      const v = emailHeadline.next(".value").first();
      if (v.length) email = textOf(v);
    }

    const phoneHeadline = section
      .find(".headline")
      .filter((_, el) => textOf($(el)) === "Телефон")
      .first();
    if (phoneHeadline.length) {
      const v = phoneHeadline.next(".value").first();
      if (v.length) phone = textOf(v);
    }
  }

  // --- Транспортний засіб ---
  let vehicleType = null;
  let vehicleMake = null;
  let vehicleModel = null;
  let vehiclePlate = null;
  let vehicleVin = null;
  let registeredInUkraine = null;

  const vehicleHeader = $(".content h3")
    .filter((_, el) => textOf($(el)).includes("Транспортний засіб"))
    .first();

  if (vehicleHeader.length) {
    const section = vehicleHeader.parent();

    const valueByLabel = (label) => {
      const headline = section
        .find(".headline")
        .filter((_, el) => textOf($(el)) === label)
        .first();
      if (!headline.length) return null;
      const value = headline.next(".value").first();
      if (!value.length) return null;
      return textOf(value);
    };

    vehicleType = valueByLabel("Тип");
    vehicleMake = valueByLabel("Марка");
    vehicleModel = valueByLabel("Модель");
    vehiclePlate = valueByLabel("Реєстраційний номер");
    vehicleVin = valueByLabel("VIN (номер кузова, шасі, рами)");

    const regHeadline = section
      .find(".headline")
      .filter((_, el) =>
        textOf($(el)).startsWith(
          "Ознака, що транспортний засіб зареєстрований в Україні"
        )
      )
      .first();
    if (regHeadline.length) {
      const v = regHeadline.next(".value").first();
      if (v.length) registeredInUkraine = textOf(v);
    }
  }

  return {
    policyNumber,
    status,
    statusDate,
    companyName,
    companyStatus,
    edrpou,
    address,
    email,
    phone,
    vehicle: {
      type: vehicleType,
      make: vehicleMake,
      model: vehicleModel,
      plate: vehiclePlate,
      vin: vehicleVin,
      registeredInUkraine
    }
  };
}
