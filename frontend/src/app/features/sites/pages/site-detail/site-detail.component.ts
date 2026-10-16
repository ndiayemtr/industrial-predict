import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, distinctUntilChanged, map, of, startWith, switchMap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { SitesApiService } from '../../data-access/sites-api.service';

type ReadError = { status: 'error'; title: string; message: string; retryable: boolean };
type CompanyState = { status: 'loading' } | { status: 'success'; data: CompanyRead } | ReadError;
type DetailState = { status: 'loading' } | ReadError | { status: 'success'; data: SiteRead; company: CompanyState };
const positive = (raw: string | null, fallback: number | null, maximum = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= maximum
    ? Number(raw) : fallback;

@Component({
  selector: 'app-site-detail', standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './site-detail.component.html', styleUrl: './site-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SiteDetailComponent {
  private readonly api = inject(SitesApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly refresh = new Subject<void>();
  private readonly companyRefresh = new Subject<void>();
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly referenceLabel = businessReferenceLabel;
  readonly state = toSignal(this.route.paramMap.pipe(
    map(params => params.get('siteId')), distinctUntilChanged(),
    switchMap(raw => {
      const id = positive(raw, null);
      if (id === null) return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
        message: 'L’identifiant du site doit être un entier positif valide. Revenez à la liste.', retryable: false });
      return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(id).pipe(
        switchMap(data => this.loadCompany(data)),
        catchError(error => of<DetailState>(this.readError(error, false))),
        startWith<DetailState>({ status: 'loading' })
      )));
    })
  ), { initialValue: { status: 'loading' } as DetailState });
  readonly listQuery = computed(() => {
    const params = this.params(), state = this.state();
    const companyId = positive(params.get('company_id'), null) ?? (state.status === 'success' ? state.data.company_id : null);
    const search = params.get('search')?.trim() ?? '';
    return { ...(companyId !== null ? { company_id: companyId } : {}),
      page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
      ...(search && search.length <= 100 ? { search } : {}) };
  });

  retry(): void {
    const state = this.state();
    if (state.status === 'error' && state.retryable) this.refresh.next();
  }
  retryCompany(): void {
    const state = this.state();
    if (state.status === 'success' && state.company.status === 'error' && state.company.retryable) this.companyRefresh.next();
  }
  display(value: string | null | undefined): string { return value?.trim() ? value : 'Non renseigné'; }

  private loadCompany(data: SiteRead): Observable<DetailState> {
    return this.companyRefresh.pipe(startWith(undefined), switchMap(() => this.references.getCompanyById(data.company_id).pipe(
      map((company): DetailState => ({ status: 'success', data, company: { status: 'success', data: company } })),
      catchError(error => of<DetailState>({ status: 'success', data, company: this.readError(error, true) })),
      startWith<DetailState>({ status: 'success', data, company: { status: 'loading' } })
    )));
  }
  private readError(error: unknown, company: boolean): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    return { status: 'error', retryable: status === 0 || status >= 500,
      title: status === 404 ? company ? 'Entreprise introuvable' : 'Site introuvable (404)'
        : company ? 'Référence entreprise indisponible' : 'Chargement impossible',
      message: status === 404 ? company ? 'La référence de cette entreprise n’est plus disponible.' : 'Ce site n’existe pas ou n’est plus disponible. Revenez à la liste.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 400 || status === 422 ? 'L’identifiant demandé n’est pas accepté par le serveur.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : company ? 'Le nom et le code de l’entreprise ne peuvent pas être chargés.' : 'Les informations du site ne peuvent pas être chargées.' };
  }
}
