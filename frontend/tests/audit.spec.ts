import { test, expect, Page } from '@playwright/test';

async function session(page: Page, role = 'TECHNICIAN', mustChange = false) {
  await page.route('**/api/v1/locations', route => route.fulfill({json: [
    {id: 'l1', group_name: 'EL POLLO LOCO', name: 'Santiago', is_active: true, revision: 0},
    {id: 'l2', group_name: 'TACO PALENQUE', name: 'Santiago', is_active: true, revision: 0},
    {id: 'l3', group_name: 'Otras ubicaciones', name: 'Oficinas Centrales', is_active: true, revision: 0},
  ]}));
  await page.route('**/api/v1/admin/report-mail', route => route.fulfill({ json: {
    enabled: true, first_send_date: '2026-09-28', to_emails: ['oscar.moncada@pleg.com.mx'], cc_emails: ['josue.acosta@pleg.com.mx', 'lupita.carrizales@pleg.com.mx'],
    revision: 0, timezone: 'America/Monterrey', next_send: '2026-09-28T09:00:00-06:00', sender: 'notificaciones@pleg.com.mx', sender_name: 'GRUPO EXPO - Recursos Humanos', smtp_configured: true,
  } }));
  await page.route('**/api/v1/admin/report-mail/runs', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/attendance/summary', route => route.fulfill({ json: { incidents: 0, leaves: 0 } }));
  await page.addInitScript(({ role, mustChange }) => {
    if (!localStorage.getItem('mi-jornada-auth')) localStorage.setItem('mi-jornada-auth', JSON.stringify({ version: 2, state: {
      user: { id: 'u1', full_name: 'Prueba Técnica', username: 'test', role, is_active: true, email: 'test@example.com', must_change_password: mustChange },
      accessToken: 'old-access', refreshToken: 'old-refresh', isAuthenticated: true, rememberMe: true,
    } }));
  }, { role, mustChange });
}

const workday = { id: 'w1', work_date: '2026-09-19', status: 'OPEN', check_in_at: '2026-09-19T15:00:00Z' };

test('admin removes and restores technician with a reason on mobile', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.setViewportSize({ width: 390, height: 844 });
  let deleted = false;
  let reason = '';
  await page.route('**/api/v1/admin/users**', route => {
    const request = route.request();
    if (request.method() === 'POST') {
      reason = request.postDataJSON().reason;
      deleted = request.url().endsWith('/delete');
      return route.fulfill({ json: {} });
    }
    const visible = !deleted || new URL(request.url()).searchParams.get('include_deleted') === 'true';
    return route.fulfill({ json: { items: visible ? [{ id: 't1', full_name: 'Persona de prueba', username: 'prueba', email: 'test@example.com', role: 'TECHNICIAN', is_active: !deleted, deleted_at: deleted ? '2026-09-28T15:00:00Z' : null }] : [], total: visible ? 1 : 0, pages: 1 } });
  });
  await page.goto('/admin/personal');
  await page.getByRole('button', { name: 'Eliminar a Persona de prueba', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Eliminar técnico', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('motivo');
  await page.getByLabel('Motivo del cambio').fill('Baja autorizada');
  await dialog.getByRole('button', { name: 'Eliminar técnico', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('Técnico eliminado');
  expect(reason).toBe('Baja autorizada');
  await expect(page.getByRole('heading', { name: 'Persona de prueba' })).toHaveCount(0);
  await page.getByLabel('Mostrar también técnicos eliminados').check();
  await expect(page.getByText('Eliminado · historial conservado')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Editar a Persona de prueba' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Restaurar a Persona de prueba' }).click();
  await page.getByLabel('Motivo del cambio').fill('Reingreso autorizado');
  await dialog.getByRole('button', { name: 'Restaurar técnico', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('restaurado como inactivo');
  await expect(page.getByRole('button', { name: 'Editar a Persona de prueba' })).toBeVisible();
});

test('administrator adds justified workday on mobile', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [{ id: 't1', full_name: 'Técnico de prueba' }] }));
  let saved: any = null;
  await page.route('**/api/v1/admin/workdays**', route => {
    if (route.request().method() === 'POST') {
      saved = route.request().postDataJSON();
      return route.fulfill({ status: 201, json: { id: 'new', work_date: '2026-09-25' } });
    }
    return route.fulfill({ json: { items: saved ? [{ id: 'new', technician_name: 'Técnico de prueba', work_date: '2026-09-25', check_in_at: '2026-09-25T15:00:00Z', status: 'OPEN', revision: 1 }] : [], total: saved ? 1 : 0 } });
  });
  await page.goto('/admin/jornadas');
  await page.getByRole('button', { name: 'Agregar jornada', exact: true }).click();
  await page.getByRole('button', { name: 'Guardar jornada', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await page.getByLabel('Técnico de la jornada').selectOption('t1');
  await page.getByLabel('Entrada de la jornada').fill('2026-09-25T09:00');
  await page.getByLabel('Justificación del registro').fill('Olvidó registrar; entrada verificada');
  await page.getByRole('button', { name: 'Guardar jornada', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('Jornada agregada');
  expect(saved.check_out_at).toBeNull();
  expect(saved.technician_id).toBe('t1');
});

test('read only cannot add journeys and operation has no assignment button', async ({ page }) => {
  await session(page, 'READ_ONLY');
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/admin/workdays**', route => route.fulfill({ json: { items: [], total: 0 } }));
  await page.route('**/api/v1/admin/dashboard', route => route.fulfill({ json: { working_now: 0, not_started: 0, finished: 0, tasks_completed: 0, tasks_pending: 0, technicians: [] } }));
  await page.goto('/admin/jornadas');
  await expect(page.getByRole('heading', { name: 'Jornadas', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Agregar jornada' })).toHaveCount(0);
  await page.goto('/admin');
  await expect(page.getByText('Técnicos en campo')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Asignar tarea' })).toHaveCount(0);
});

test('mandatory personal password blocks navigation and returns to login', async ({page}) => {
  await session(page, 'TECHNICIAN', true);
  await page.setViewportSize({width: 390, height: 844});
  await page.route('**/api/v1/auth/change-password', route => route.fulfill({json: {message: 'Guardada'}}));
  await page.route('**/api/v1/auth/logout', route => route.fulfill({json: {}}));
  await page.goto('/');
  await expect(page).toHaveURL(/mi-cuenta/);
  await page.getByLabel('Contraseña actual o temporal').fill('Temporary2026!');
  await page.getByLabel('Nueva contraseña', {exact: true}).fill('Personal2026!');
  await page.getByLabel('Confirmar nueva contraseña').fill('NotMatching2026!');
  await page.getByRole('button', {name: 'Guardar contraseña', exact: true}).click();
  await expect(page.getByRole('alert')).toContainText('no coinciden');
  await page.getByLabel('Confirmar nueva contraseña').fill('Personal2026!');
  await page.screenshot({path: 'test-results/personal-password-mobile.png', fullPage: true});
  const sent = page.waitForRequest(r => r.url().endsWith('/auth/change-password'));
  await page.getByRole('button', {name: 'Guardar contraseña', exact: true}).click();
  expect((await sent).postDataJSON().new_password).toBe('Personal2026!');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('status')).toContainText('Contraseña guardada');
});

test('existing session follows server password requirement', async ({page}) => {
  await session(page);
  await page.route('**/api/v1/workdays/today', route => route.fulfill({status: 403, json: {detail: {code: 'PASSWORD_CHANGE_REQUIRED'}}}));
  await page.route('**/api/v1/tasks/today', route => route.fulfill({json: []}));
  await page.goto('/');
  await expect(page).toHaveURL(/mi-cuenta/);
  await expect(page.getByRole('heading', {name: 'Establece tu contraseña personal'})).toBeVisible();
});

test('recovery link hides token from URL and handles expiration', async ({page}) => {
  const token = 'x'.repeat(43);
  await page.route('**/api/v1/auth/reset-password', route => route.fulfill({status: 400, json: {detail: 'El enlace no es válido o ya venció. Solicita uno nuevo.'}}));
  await page.goto('/recuperar-contrasena#token='+token);
  await expect(page).toHaveURL(/\/recuperar-contrasena$/);
  await page.getByLabel('Nueva contraseña', {exact: true}).fill('Personal2026!');
  await page.getByLabel('Confirmar nueva contraseña').fill('Personal2026!');
  const sent = page.waitForRequest(r => r.url().endsWith('/auth/reset-password'));
  await page.getByRole('button', {name: 'Guardar nueva contraseña', exact: true}).click();
  expect((await sent).postDataJSON().token).toBe(token);
  await expect(page.getByRole('alert')).toContainText('ya venció');
  await page.getByRole('button', {name: 'Solicitar otro enlace'}).click();
  await page.getByLabel('Correo electrónico').fill('tech@example.com');
  await page.route('**/api/v1/auth/forgot-password', route => route.fulfill({json: {message: 'Si el correo corresponde a una cuenta activa, recibirás un enlace.'}}));
  await page.getByRole('button', {name: 'Solicitar enlace', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('Si el correo');
});

test('technician chooses the correct Santiago branch from catalog', async ({page}) => {
  await session(page);
  await page.setViewportSize({width:390,height:844});
  await page.route('**/api/v1/workdays/today', route => route.fulfill({json: {status:'WORKING',workday}}));
  await page.route('**/api/v1/tasks/today', route => route.fulfill({json: []}));
  await page.route('**/api/v1/tasks/unplanned', route => route.fulfill({json: {id:'new-task',title:'Revisión',status:'PENDING',location_id:'l2',location_name:'TACO PALENQUE · Santiago'}}));
  await page.goto('/');
  await page.getByRole('button', {name: 'AGREGAR ACTIVIDAD'}).click();
  await page.getByPlaceholder('Ej. Revisión de equipo').fill('Revisión');
  await page.getByRole('button', {name: 'GUARDAR', exact: true}).click();
  await expect(page.getByText('Selecciona la sucursal relacionada con la tarea.',{exact:true})).toBeVisible();
  const select = page.getByLabel('Sucursal relacionada con la tarea *');
  await expect(select.getByRole('option', {name:'EL POLLO LOCO · Santiago',exact:true})).toHaveCount(1);
  await select.selectOption('l2');
  await page.screenshot({path: 'test-results/branch-task-mobile.png',fullPage:true});
  const sent = page.waitForRequest(r => r.url().endsWith('/tasks/unplanned'));
  await page.getByRole('button', {name:'GUARDAR',exact:true}).click();
  expect((await sent).postDataJSON().location_id).toBe('l2');
  await expect(page.getByText('TACO PALENQUE · Santiago',{exact:true})).toBeVisible();
});

test('weekly reports allow recipient updates and download PDF on mobile', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  await page.goto('/admin/reportes');
  await expect(page.getByLabel('Para', { exact: true })).toHaveValue('oscar.moncada@pleg.com.mx');
  await expect(page.getByText(/lunes, 28 de septiembre de 2026/)).toBeVisible();
  await page.getByLabel('Con copia', { exact: true }).fill('other@example.com');
  const save = page.waitForRequest(req => req.method() === 'PATCH' && req.url().endsWith('/admin/report-mail'));
  await page.getByRole('button', { name: 'Guardar programación' }).click();
  expect((await save).postDataJSON().cc_emails).toEqual(['other@example.com']);
  await expect(page.getByRole('status')).toContainText('Programación guardada');
  await page.route('**/api/v1/admin/report-mail/pdf?**', route => route.fulfill({ contentType: 'application/pdf', body: '%PDF-1.4 test', headers: { 'Content-Disposition': 'attachment; filename="test.pdf"' } }));
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: 'DESCARGAR PDF DE ASISTENCIAS' }).click();
  expect((await download).suggestedFilename()).toContain('asistencias_');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: 'test-results/weekly-report-mobile.png', fullPage: true });
});

test('badges render and task failures do not erase an open workday', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page);
  await page.route('**/api/v1/workdays/today', route => route.fulfill({ json: { status: 'WORKING', workday } }));
  await page.route('**/api/v1/tasks/today', route => route.fulfill({ status: 503, json: {} }));
  await page.goto('/');
  await expect(page.getByText('✅ JORNADA ACTIVA')).toBeVisible();
  await expect(page.getByText('No se pudieron actualizar las tareas.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'REGISTRAR SALIDA' })).toBeVisible();
  await expect(page.getByText('undefined', { exact: true })).toHaveCount(0);
  await page.route('**/api/v1/tasks/today', route => route.fulfill({ json: [] }));
  await page.getByRole('button', { name: 'Reintentar tareas' }).click();
  await expect(page.getByText('No tienes tareas asignadas hoy.')).toBeVisible();
  await page.screenshot({ path: 'test-results/technician-mobile.png', fullPage: true });
});

test('workday errors offer retry instead of a false check-in state', async ({ page }) => {
  await session(page);
  await page.route('**/api/v1/workdays/today', route => route.fulfill({ status: 503, json: {} }));
  await page.route('**/api/v1/tasks/today', route => route.fulfill({ json: [] }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Reintentar', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'REGISTRAR ENTRADA' })).toHaveCount(0);
});

test('reports preserve minutes and display the API time once', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/admin/reports?**', route => route.fulfill({ json: [{ technician_id: 't1', technician_name: 'Técnico Prueba', days_worked: 1, total_minutes: 539, total_hours: 9, avg_check_in: '1:30 PM', avg_check_out: null, tasks_assigned: 1, tasks_completed: 1, tasks_pending: 0 }] }));
  await page.goto('/admin/reportes');
  await page.getByRole('button', { name: /Generar/i }).click();
  await expect(page.getByRole('cell', { name: '1:30 PM', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '8 h 59 min', exact: true }).first()).toBeVisible();
  await expect(page.getByText('1:30 PM AM')).toHaveCount(0);
});

test('users can paginate and the modal supports Escape and focus return', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.route('**/api/v1/admin/users**', route => {
    const number = Number(new URL(route.request().url()).searchParams.get('page') || 1);
    return route.fulfill({ json: { items: [{ id: 'u' + number, username: 'user' + number, full_name: 'Usuario ' + number, email: 'u@example.com', role: 'TECHNICIAN', is_active: true }], total: 21, pages: 2 } });
  });
  await page.goto('/admin/usuarios');
  await page.getByRole('button', { name: 'Siguiente' }).click();
  await expect(page.getByRole('heading', { name: 'Usuario 2', exact: true })).toBeVisible();
  const create = page.getByRole('button', { name: 'Agregar persona' });
  await create.click();
  const dialog = page.getByRole('dialog', { name: 'Agregar persona' });
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('input').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(create).toBeFocused();
});

test('parallel 401 responses share a refresh and retain the new tokens', async ({ page }) => {
  await session(page);
  let refreshes = 0;
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/refresh')) {
      refreshes++;
      return route.fulfill({ json: { access_token: 'new-access', refresh_token: 'new-refresh' } });
    }
    if (route.request().headers().authorization !== 'Bearer new-access') return route.fulfill({ status: 401, json: {} });
    return route.fulfill({ json: path.endsWith('/tasks/today') ? [] : { status: 'WORKING', workday } });
  });
  await page.goto('/');
  await expect(page.getByText('✅ JORNADA ACTIVA')).toBeVisible();
  expect(refreshes).toBe(1);
  const state = await page.evaluate(() => JSON.parse(localStorage.getItem('mi-jornada-auth')!).state);
  expect(state.refreshToken).toBe('new-refresh');
});

test('temporary refresh failure keeps the session available for retry', async ({ page }) => {
  await session(page);
  await page.route('**/api/v1/**', route => route.fulfill({ status: route.request().url().endsWith('/auth/refresh') ? 503 : 401, json: {} }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Reintentar', exact: true })).toBeVisible();
  expect(new URL(page.url()).pathname).toBe('/');
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('mi-jornada-auth')!).state.isAuthenticated)).toBe(true);
});

test('two tabs coordinate refresh rotation', async ({ context, page }) => {
  const other = await context.newPage();
  await session(page);
  await session(other);
  let refreshes = 0;
  const waitingPages = new Set<Page>();
  let bothExpired!: () => void;
  const gate = new Promise<void>(resolve => { bothExpired = resolve; });
  await context.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/auth/refresh')) {
      await gate;
      refreshes++;
      return route.fulfill({ json: { access_token: 'new-access', refresh_token: 'new-refresh' } });
    }
    if (route.request().headers().authorization !== 'Bearer new-access') {
      waitingPages.add(route.request().frame().page());
      if (waitingPages.size === 2) bothExpired();
      return route.fulfill({ status: 401, json: {} });
    }
    return route.fulfill({ json: path.endsWith('/tasks/today') ? [] : { status: 'WORKING', workday } });
  });
  await Promise.all([page.goto('/'), other.goto('/')]);
  await expect(page.getByText('✅ JORNADA ACTIVA')).toBeVisible();
  await expect(other.getByText('✅ JORNADA ACTIVA')).toBeVisible();
  expect(refreshes).toBe(1);
});

test.describe('PWA', () => {
  test.use({ serviceWorkers: 'allow' });
  test('the installed shell reloads without a network connection', async ({ page, context }) => {
    await page.goto('/login');
    await page.evaluate(async () => { await navigator.serviceWorker.ready; });
    await page.reload();
    await expect(page.getByRole('button', { name: 'INICIAR SESIÓN' })).toBeVisible();
    await context.setOffline(true);
    await page.reload();
    await expect(page.getByRole('button', { name: 'INICIAR SESIÓN' })).toBeVisible();
    await expect(page.getByText('Sin conexión. Conéctate para consultar y registrar tu jornada.')).toBeVisible();
  });
});

test('personal edits access and technician data together and filters by role', async ({ page }) => {
  await session(page, 'ADMIN');
  let person = { id: 'u2', username: 'aidan', full_name: 'Aidan Avila', email: 'aidan@example.com', role: 'TECHNICIAN', is_active: true, technician: { id: 't2', phone: null as string | null, employee_number: null as string | null } };
  let payload: any;
  await page.route('**/api/v1/admin/users**', route => {
    if (route.request().method() === 'PATCH') {
      payload = route.request().postDataJSON();
      person = { ...person, full_name: payload.full_name, technician: { ...person.technician, phone: payload.phone, employee_number: payload.employee_number } };
      return route.fulfill({ json: person });
    }
    const role = new URL(route.request().url()).searchParams.get('role');
    return route.fulfill({ json: { items: role === 'ADMIN' ? [] : [person], total: role === 'ADMIN' ? 0 : 1, pages: 1 } });
  });
  await page.goto('/admin/tecnicos');
  await expect(page).toHaveURL(/personal\?rol=TECHNICIAN/);
  await page.getByRole('button', { name: 'Editar a Aidan Avila' }).click();
  await page.getByLabel('Nombre completo').fill('Aidan Editado');
  await page.getByLabel('Teléfono').fill('8112345678');
  await page.getByLabel('Número de empleado').fill('TEC-01');
  await page.getByRole('button', { name: 'Guardar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Aidan Editado' })).toBeVisible();
  await expect(page.getByText('8112345678', { exact: true })).toBeVisible();
  expect(payload).toEqual({ full_name: 'Aidan Editado', phone: '8112345678', employee_number: 'TEC-01' });
  await expect(page.getByRole('link', { name: 'Jornada y tareas' })).toHaveAttribute('href', '/admin/personal/tecnico/t2');
  await page.getByRole('button', { name: 'Administradores', exact: true }).click();
  await expect(page.getByText('No hay personas que coincidan con los filtros.')).toBeVisible();
});

test('technician requests vacation using calendar dates without approving it', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page);
  let rows: any[] = [];
  let payload: any;
  await page.route('**/api/v1/attendance/leaves**', route => {
    if (route.request().method() === 'POST') {
      payload = route.request().postDataJSON();
      rows = [{ ...payload, id: 'l1', technician_name: 'Prueba Técnica', status: 'PENDING', working_days: 3 }];
      return route.fulfill({ status: 201, json: { id: 'l1', status: 'PENDING' } });
    }
    return route.fulfill({ json: rows });
  });
  await page.goto('/ausencias');
  await page.getByRole('button', { name: 'Solicitar vacaciones o permiso', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Primer día').fill('2027-01-08');
  await dialog.getByLabel('Último día').fill('2027-01-11');
  await dialog.getByLabel('Motivo', { exact: true }).fill('Vacaciones familiares');
  await expect(dialog.getByText('3 días laborales solicitados.', { exact: false })).toBeVisible();
  await dialog.getByRole('button', { name: 'Enviar solicitud' }).click();
  await expect(page.getByText('Solicitud enviada. Requiere aprobación del administrador.')).toBeVisible();
  expect(payload.technician_id).toBeUndefined();
  await expect(page.getByRole('button', { name: 'Aprobar', exact: true })).toHaveCount(0);
  await expect(page.getByText('Pendiente', { exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/absence-mobile.png', fullPage: true });
});

test('admin approval requires a reason and keeps rejected requests visible', async ({ page }) => {
  await session(page, 'ADMIN');
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/attendance/summary', route => route.fulfill({ json: { incidents: 0, leaves: 1 } }));
  let row = { id: 'l1', technician_name: 'Aidan Avila', status: 'PENDING', kind: 'VACATION', start_date: '2027-01-08', end_date: '2027-01-11', working_days: 3, reason: 'Vacaciones familiares', review_note: '' };
  await page.route('**/api/v1/attendance/leaves**', route => {
    if (route.request().method() === 'PATCH') {
      const payload = route.request().postDataJSON();
      if (!payload.note.trim()) return route.fulfill({ status: 422, json: { detail: 'Indica el motivo de la resolución' } });
      row = { ...row, status: payload.status, review_note: payload.note };
      return route.fulfill({ json: { status: row.status } });
    }
    return route.fulfill({ json: [row] });
  });
  await page.goto('/admin/asistencia');
  await page.getByRole('button', { name: 'Aprobar', exact: true }).click();
  await page.getByRole('button', { name: 'Guardar resolución' }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await page.getByLabel('Motivo de la resolución').fill('Autorizado por supervisor');
  await page.getByRole('button', { name: 'Guardar resolución' }).click();
  await expect(page.getByText('Aprobada', { exact: true })).toBeVisible();
  await expect(page.getByText('Resolución: Autorizado por supervisor')).toBeVisible();
});

test('early checkout shows server explanation and sends the technician reason', async ({ page, context }) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 25.68, longitude: -100.31 });
  await session(page);
  await page.route('**/api/v1/tasks/today', route => route.fulfill({ json: [] }));
  let closed = false;
  await page.route('**/api/v1/workdays/today', route => route.fulfill({ json: { status: closed ? 'FINISHED' : 'WORKING', workday, can_start_day: false, scheduled_exit: '2026-09-19T13:00:00-06:00', early_exit: true } }));
  let payload: any;
  await page.route('**/api/v1/workdays/check-out', route => {
    payload = route.request().postDataJSON();
    if (!payload.early_exit_reason) return route.fulfill({ status: 422, json: { detail: 'Salida anticipada: indica un motivo.' } });
    closed = true;
    return route.fulfill({ json: { ...workday, work_date: new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Monterrey' }).format(new Date()), status: 'CLOSED' } });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'REGISTRAR SALIDA' }).click();
  await page.getByRole('button', { name: 'TERMINAR JORNADA' }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('Salida anticipada');
  await page.getByLabel('Motivo de salida anticipada').fill('Permiso para cita');
  await page.getByRole('button', { name: 'TERMINAR JORNADA' }).click();
  await expect(page.getByText('✅ JORNADA FINALIZADA')).toBeVisible();
  expect(payload.early_exit_reason).toBe('Permiso para cita');
});

test('admin can edit, annul and restore workdays with a required reason on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await session(page, 'ADMIN');
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  let row = { id: 'w-edit', technician_id: 't1', technician_name: 'Aidan Avila', work_date: '2026-09-19', check_in_at: '2026-09-19T15:00:00Z', check_out_at: '2026-09-20T01:00:00Z', duration_minutes: 600, status: 'CLOSED', is_void: false, revision: 0, tasks_assigned: 2, tasks_completed: 2 };
  await page.route('**/api/v1/admin/workdays**', route => {
    if (route.request().method() === 'PATCH') {
      const data = route.request().postDataJSON();
      if (!data.reason.trim()) return route.fulfill({ status: 422, json: { detail: 'Escribe un motivo' } });
      const url = route.request().url();
      row = { ...row, revision: row.revision + 1, is_void: url.endsWith('/void') ? true : url.endsWith('/restore') ? false : row.is_void, duration_minutes: url.endsWith('/w-edit') ? 240 : row.duration_minutes };
      return route.fulfill({ json: row });
    }
    const include = new URL(route.request().url()).searchParams.get('include_void') === 'true';
    const items = !row.is_void || include ? [row] : [];
    return route.fulfill({ json: { items, total: items.length, pages: 1 } });
  });
  await page.goto('/admin/jornadas');
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  await page.getByLabel('Salida', { exact: true }).fill('2026-09-19T13:00');
  await page.getByRole('button', { name: 'Guardar cambio' }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await page.getByLabel('Motivo del cambio').fill('Corregir horas de prueba');
  await page.getByRole('button', { name: 'Guardar cambio' }).click();
  await expect(page.getByText('4h 00min').last()).toBeVisible();
  await page.getByRole('button', { name: 'Eliminar', exact: true }).click();
  await page.getByLabel('Motivo del cambio').fill('Eliminar jornada de prueba');
  await page.getByRole('button', { name: 'Anular jornada', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Eliminar', exact: true })).toHaveCount(0);
  await page.getByLabel('Mostrar también jornadas anuladas (pulsa Buscar)').check();
  await page.getByRole('button', { name: 'Buscar', exact: true }).click();
  await expect(page.getByText('ANULADA', { exact: true }).last()).toBeVisible();
  await page.getByRole('button', { name: 'Restaurar', exact: true }).click();
  await page.getByLabel('Motivo del cambio').fill('Restaurar jornada');
  await page.getByRole('button', { name: 'Guardar cambio' }).click();
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Editar', exact: true }).scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/workday-actions-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1280, height: 900 });
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeInViewport();
});


test('read only panel hides mutations and keeps report downloads', async ({ page }) => {
  await session(page, 'READ_ONLY');
  await page.route('**/api/v1/admin/technicians**', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/admin/tasks?**', route => route.fulfill({ json: [{ id: 't1', title: 'Inspección', technician_id: 'tech', assigned_date: '2026-09-21', status: 'PENDING', priority: 'NORMAL' }] }));
  await page.route('**/api/v1/admin/reports?**', route => route.fulfill({ json: [] }));
  await page.goto('/admin/tareas');
  await expect(page.getByText('Inspección', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'NUEVA TAREA' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Editar', exact: true })).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Personal', exact: true })).toHaveCount(0);
  await page.goto('/admin/reportes');
  await expect(page.getByRole('button', { name: /Generar/i })).toBeVisible();
  await expect(page.getByText('Reportes semanales por correo')).toHaveCount(0);
});

test('my account presents profile before password form', async ({ page }) => {
  await session(page, 'READ_ONLY');
  await page.goto('/mi-cuenta');
  await expect(page.getByText('Rol: Solo lectura', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Contraseña actual o temporal')).toHaveCount(0);
  await page.getByRole('button', { name: 'Cambiar contraseña', exact: true }).click();
  await expect(page.getByLabel('Contraseña actual o temporal')).toBeVisible();
  await page.getByRole('button', { name: 'Cancelar cambio' }).click();
  await expect(page.getByLabel('Contraseña actual o temporal')).toHaveCount(0);
});

test('technician declares night and continues into daytime with geolocation', async ({ page, context }) => {
  await context.grantPermissions(['geolocation']);
  await context.setGeolocation({ latitude: 25.68, longitude: -100.31 });
  await session(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('**/api/v1/attendance/leaves?**', route => route.fulfill({ json: [] }));
  const plans: any[] = [];
  await page.route('**/api/v1/night-plans**', route => {
    if (route.request().method() === 'POST') {
      const data = route.request().postDataJSON();
      plans.push({ ...data, id: 'n1', status: 'PENDING', technician_name: 'Prueba Técnica', reminder_at: data.work_date + 'T21:00:00-06:00' });
      return route.fulfill({ status: 201, json: { id: 'n1', status: 'PENDING' } });
    }
    return route.fulfill({ json: plans });
  });
  await page.goto('/ausencias');
  await page.getByRole('button', { name: 'Turnos nocturnos', exact: true }).click();
  await page.getByRole('button', { name: 'Avisar trabajo nocturno', exact: true }).click();
  await page.getByLabel('Hora del recordatorio (Monterrey)').fill('21:00');
  await page.getByLabel('Motivo o trabajo programado').fill('Mantenimiento en sucursal');
  await page.getByRole('button', { name: 'Guardar programación' }).click();
  await expect(page.getByText('Pendiente de validación · Recordatorio:', { exact: false })).toBeVisible();
  expect(plans[0].replaces_day).toBe(true);
  expect(plans[0].rest_next_day).toBe(false);
  let transitioned = false;
  await page.route('**/api/v1/tasks/today', route => route.fulfill({ json: [] }));
  await page.route('**/api/v1/workdays/today', route => route.fulfill({ json: { status: 'WORKING', workday: { ...workday, shift_kind: transitioned ? 'DAY' : 'NIGHT' }, can_start_day: !transitioned, scheduled_exit: null } }));
  await page.route('**/api/v1/workdays/continue-day', route => {
    expect(route.request().postDataJSON().latitude).toBe(25.68);
    transitioned = true;
    return route.fulfill({ json: { ...workday, shift_kind: 'DAY' } });
  });
  await page.goto('/');
  await expect(page.getByText('🌙 NOCTURNA ACTIVA')).toBeVisible();
  await page.getByRole('button', { name: 'Continuar con turno diurno' }).click();
  await page.getByRole('button', { name: 'Registrar cambio de turno' }).click();
  await expect(page.getByText('✅ JORNADA ACTIVA')).toBeVisible();
  expect(transitioned).toBe(true);
});
