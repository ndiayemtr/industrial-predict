import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subject, catchError, distinctUntilChanged, map, of, startWith, switchMap } from 'rxjs';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { CompaniesApiService } from '../../data-access/companies-api.service';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';

type DetailState =
  | { status: 'loading' }
  | { status: 'success'; data: CompanyRead }
  | { status: 'error'; title: string; message: string; retryable: boolean };

@Component({
  selector: 'app-company-detail',
  standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './company-detail.component.html',
  styleUrl: './company-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CompanyDetailComponent {
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly createdCompanyId = inject(Router).currentNavigation()?.extras.state?.['createdCompanyId'];
  readonly updatedCompanyId = inject(Router).currentNavigation()?.extras.state?.['updatedCompanyId'];
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(CompaniesApiService);
  private readonly refresh = new Subject<void>();
  readonly listQuery = toSignal(this.route.queryParamMap.pipe(map(params => {
    const positive = (raw: string | null, fallback: number, maximum = Number.MAX_SAFE_INTEGER) =>
      raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw))
        && Number(raw) >= 1 && Number(raw) <= maximum ? Number(raw) : fallback;
    const search = params.get('search')?.trim() ?? '';
    return { page: positive(params.get('page'), 1), page_size: positive(params.get('page_size'), 20, 100),
      ...(search && search.length <= 100 ? { search } : {}) };
  })), { requireSync: true });

  readonly state = toSignal(this.route.paramMap.pipe(
    map(params => params.get('companyId')),
    distinctUntilChanged(),
    switchMap(raw => {
      // Route validation is a UI guard, not a backend authorization check.
      if (raw === null || !/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) < 1) {
        return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
          message: 'L’identifiant de l’entreprise doit être un entier positif valide. Revenez à la liste.', retryable: false });
      }
      return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(Number(raw)).pipe(
        map((data): DetailState => ({ status: 'success', data })),
        catchError((error: unknown) => {
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          return of<DetailState>({ status: 'error',
            title: status === 404 ? 'Entreprise introuvable' : 'Chargement impossible',
            message: status === 404 ? 'Cette entreprise n’existe pas ou n’est plus disponible. Revenez à la liste.'
              : status === 422 || status === 400 ? 'L’identifiant demandé n’est pas accepté par le serveur. Revenez à la liste.'
              : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
              : 'Les informations de l’entreprise ne peuvent pas être chargées.',
            retryable: status === 0 || status >= 500 });
        }),
        startWith<DetailState>({ status: 'loading' })
      )));
    })
  ), { initialValue: { status: 'loading' } as DetailState });

  retry(): void {
    const state = this.state();
    if (state.status === 'error' && state.retryable) this.refresh.next();
  }

  display(value: string | null | undefined): string {
    return value?.trim() ? value : 'Non renseigné';
  }
}
